"""Cómputo estructurado de las sugerencias de un día (reutilizable).

Corre el pipeline de análisis (modelo → selección de lado → cuotas → edge →
veredicto → Kelly) sobre los partidos programados de una fecha y devuelve una
lista de dicts. Lo consumen el reporte HTML editorial y el resumen social.

No coloca apuestas: sólo analiza y describe.
"""
from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from core.utils import utcnow
from execution.functions.fees import taker_fee_usdc
from execution.functions.slippage_estimator import estimate
from optimization.functions.bet_sizer import size_single
from portfolio.schemas.portfolio_state import PortfolioState
from research.functions import build_strategy_opportunity, get_event_prediction, pick_side
from research.functions.odds_source import SqliteOddsSource
from risk.functions.evaluate import evaluate
from tournaments.registry import get_adapter, get_config, load_active_strategy


def _f(x) -> float | None:
    return float(x) if x is not None else None


def _complete_set_quote(markets) -> dict[str, Any]:
    """Coste ejecutable mínimo de cubrir H/D/A; nunca propone una orden."""
    required = ("HOME_WIN", "DRAW", "AWAY_WIN")
    by_outcome = {market.model_outcome: market for market in markets}
    if any(outcome not in by_outcome for outcome in required):
        return {}
    legs = [by_outcome[outcome] for outcome in required]
    if any(
        leg.best_ask is None or leg.best_ask_size is None
        or leg.min_order_size is None or leg.fee_rate_bps is None
        for leg in legs
    ):
        return {"complete_set_status": "INCOMPLETE"}
    shares = max(leg.min_order_size for leg in legs)
    asks = {outcome: leg.best_ask for outcome, leg in zip(required, legs, strict=True)}
    if shares <= 0 or any(leg.best_ask_size < shares for leg in legs):
        return {"complete_set_status": "INCOMPLETE", "complete_set_asks": asks}
    ask_sum = sum(asks.values(), Decimal(0))
    fees = sum(
        (taker_fee_usdc(shares, leg.best_ask, leg.fee_rate_bps) for leg in legs),
        Decimal(0),
    )
    all_in = ask_sum + fees / shares
    profit = shares * (Decimal(1) - all_in)
    return {
        "complete_set_status": "CANDIDATE_REVIEW" if profit > 0 else "NO_EDGE",
        "complete_set_asks": {outcome: _f(price) for outcome, price in asks.items()},
        "complete_set_ask_sum": _f(ask_sum),
        "complete_set_all_in": _f(all_in),
        "complete_set_shares": _f(shares),
        "complete_set_profit": _f(profit),
    }


def _execution_plan(opp, verdict: str, sizing) -> dict[str, Any]:
    """Valora costes públicos; sólo AUTO completo se convierte en compra simulada."""
    plan: dict[str, Any] = {
        "action": "NO_TRADE",
        "stake": 0.0,
        "evaluated_stake": 0.0,
        "expected_avg_price": None,
        "slippage_pct": None,
        "base_fee_bps": opp.fee_rate_bps,
        "fee_usdc": None,
        "net_edge": None,
        "execution_reason": None,
    }
    if sizing.skipped or sizing.size_usdc <= 0:
        plan["execution_reason"] = "sizing omitido"
        return plan

    size = sizing.size_usdc
    plan["evaluated_stake"] = float(size)
    missing = [
        name for name, value in (
            ("best ask", opp.best_ask),
            ("top asks", opp.ask_levels),
            ("base fee", opp.fee_rate_bps),
            ("tick size", opp.tick_size),
            ("minimum order size", opp.min_order_size),
        ) if value is None or value == ()
    ]
    if missing:
        plan["execution_reason"] = "faltan datos de ejecución: " + ", ".join(missing)
        return plan

    slippage = estimate(opp.polymarket_token_id, size, orderbook=list(opp.ask_levels))
    plan["expected_avg_price"] = _f(slippage.expected_avg_price)
    plan["slippage_pct"] = _f(slippage.slippage_pct)
    if not slippage.fully_filled or slippage.expected_avg_price is None:
        plan["execution_reason"] = "profundidad insuficiente para el sizing evaluado"
        return plan

    shares = size / slippage.expected_avg_price
    if shares < opp.min_order_size:
        plan["execution_reason"] = "sizing inferior al mínimo del mercado"
        return plan

    fee = taker_fee_usdc(shares, slippage.expected_avg_price, opp.fee_rate_bps)
    net_edge = opp.model_probability - slippage.expected_avg_price - fee / shares
    plan.update({"fee_usdc": float(fee), "net_edge": float(net_edge)})
    if verdict != "AUTO":
        plan["execution_reason"] = f"veredicto {verdict}: requiere NO_TRADE"
    elif net_edge <= 0:
        plan["execution_reason"] = "edge neto no positivo tras fee y slippage"
    else:
        plan.update({"action": "SIMULATED_BUY", "stake": float(size)})
    return plan


def compute(
    date: str,
    tournament_id: str = "liga_mx_2026",
    *,
    market_source: Callable | None = None,
    bankroll: float = 1000.0,
    source_name: str = "polymarket",
    allow_draft: bool = False,
) -> dict[str, Any]:
    """Devuelve {strategy, date, generated_at, rows:[...]} con una fila por partido."""
    strat = load_active_strategy(tournament_id, require_approved=not allow_draft)
    if strat is None:
        raise ValueError(f"No hay estrategia activa aprobada para {tournament_id}")

    cfg = get_config(tournament_id)
    reader = getattr(get_adapter(tournament_id), "reader", None)
    if reader is None:
        raise ValueError(f"El adapter de {tournament_id} no expone un reader")
    odds = market_source or SqliteOddsSource(tournament_id, source=source_name)
    portfolio = PortfolioState(
        bankroll_usdc=Decimal(str(bankroll)), drawdown_7d=Decimal(0),
        open_positions=[], exposure_by_participant={}, as_of=utcnow(),
    )

    fixtures = reader.query(
        "SELECT id FROM fixture WHERE status='scheduled' AND kickoff_utc LIKE ? "
        "ORDER BY kickoff_utc",
        (f"{date}%",),
    )

    rows: list[dict[str, Any]] = []
    for f in fixtures:
        pred = get_event_prediction(f["id"], tournament_id)
        if pred is None:
            continue
        markets = odds(pred)
        pk = pick_side(pred, strat.side_criterion, strat.blend_weight)
        side = pk["side"]
        pick_team = pred.participant_home if side == "HOME_WIN" else pred.participant_away
        comp = pred.components
        poisson_result = None
        dixon_coles_result = None
        if cfg.sport == "football":
            from research.functions.poisson_loader import (
                dixon_coles_result_probs,
                match_result_probs,
            )

            poisson_result = match_result_probs(tournament_id, pred.event_id)
            dixon_coles_result = dixon_coles_result_probs(tournament_id, pred.event_id)

        row: dict[str, Any] = {
            "fixture_id": f["id"],
            "home": pred.participant_home,
            "away": pred.participant_away,
            "kickoff": pred.event_start_utc.isoformat(),
            "phase": pred.event_phase,
            "pick_side": side,
            "pick_team": pick_team,
            "confidence": pred.model_confidence.value,
            "sample_size": pred.sample_size,
            "model_version": pred.model_version,
            "elo": _f(comp.get("elo", {}).get(side)),
            "bayes": _f(comp.get("bayes", {}).get(side)),
            "trueskill": _f(comp.get("trueskill", {}).get(side)),
            "poisson": (
                _f(poisson_result["home" if side == "HOME_WIN" else "away"])
                if poisson_result
                else None
            ),
            "poisson_draw": _f(poisson_result["draw"]) if poisson_result else None,
            "dixon_coles": (
                _f(dixon_coles_result["home" if side == "HOME_WIN" else "away"])
                if dixon_coles_result else None
            ),
            **(_complete_set_quote(markets) if cfg.sport == "football" else {}),
        }

        if not markets:
            row.update({"verdict": "SKIP", "reason": "sin cuota de mercado",
                        "model_prob": _f(pk["model_prob"]), "market_prob": None,
                        "edge": None, "stake": 0.0, "action": "NO_TRADE"})
            rows.append(row)
            continue

        target_probs = poisson_result if strat.bet_type == "double_chance" else None
        opp = build_strategy_opportunity(pred, markets, strat, poisson_result=target_probs)
        if opp is None:
            row.update({"verdict": "SKIP", "reason": "warmup / filtro Bayes",
                        "model_prob": _f(pk["model_prob"]), "market_prob": None,
                        "edge": None, "stake": 0.0, "action": "NO_TRADE"})
            rows.append(row)
            continue

        verdict = evaluate(opp, strat, portfolio)
        sizing = size_single(verdict, strat)
        verdict_name = verdict.verdict.value
        reason = (verdict.reasons[0] if verdict.reasons
                  else (verdict.blocking_rules[0] if verdict.blocking_rules else ""))
        row.update({
            "verdict": verdict_name,
            "reason": reason,
            "model_prob": _f(opp.model_probability),
            "market_prob": _f(opp.market_probability),
            "edge": _f(opp.edge),
            "condition_id": opp.polymarket_condition_id,
            "token_id": opp.polymarket_token_id,
            "question": opp.question,
            "outcome": opp.outcome,
            "rules": opp.rules,
            "best_ask": _f(opp.best_ask),
            "best_ask_size": _f(opp.best_ask_size),
            "top_asks": [[_f(price), _f(size)] for price, size in opp.ask_levels[:3]],
            "volume_usdc": _f(opp.market_volume_usdc),
            "liquidity_usdc": _f(opp.market_liquidity_usdc),
            "tick_size": _f(opp.tick_size),
            "min_order_size": _f(opp.min_order_size),
            **_execution_plan(opp, verdict_name, sizing),
        })
        rows.append(row)

    return {
        "strategy": strat.strategy_id,
        "side_criterion": strat.side_criterion,
        "kelly_fraction": _f(strat.kelly_fraction),
        "tournament_id": tournament_id,
        "tournament_name": cfg.display_name,
        "date": date,
        "bankroll": bankroll,
        "source": source_name,
        "generated_at": utcnow().isoformat(),
        "rows": rows,
    }
