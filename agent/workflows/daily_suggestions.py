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
from optimization.functions.bet_sizer import size_single
from portfolio.schemas.portfolio_state import PortfolioState
from research.functions import build_strategy_opportunity, get_event_prediction, pick_side
from research.functions.odds_source import SqliteOddsSource
from risk.functions.evaluate import evaluate
from tournaments.registry import get_adapter, get_config, load_active_strategy


def _f(x) -> float | None:
    return float(x) if x is not None else None


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
        if cfg.sport == "football":
            from research.functions.poisson_loader import match_result_probs

            poisson_result = match_result_probs(tournament_id, pred.event_id)

        row: dict[str, Any] = {
            "fixture_id": f["id"],
            "home": pred.participant_home,
            "away": pred.participant_away,
            "kickoff": pred.event_start_utc.isoformat(),
            "phase": pred.event_phase,
            "pick_side": side,
            "pick_team": pick_team,
            "confidence": pred.model_confidence.value,
            "elo": _f(comp.get("elo", {}).get(side)),
            "bayes": _f(comp.get("bayes", {}).get(side)),
            "trueskill": _f(comp.get("trueskill", {}).get(side)),
            "poisson": (
                _f(poisson_result["home" if side == "HOME_WIN" else "away"])
                if poisson_result
                else None
            ),
            "poisson_draw": _f(poisson_result["draw"]) if poisson_result else None,
        }

        if not markets:
            row.update({"verdict": "SKIP", "reason": "sin cuota de mercado",
                        "model_prob": _f(pk["model_prob"]), "market_prob": None,
                        "edge": None, "stake": 0.0})
            rows.append(row)
            continue

        target_probs = poisson_result if strat.bet_type == "double_chance" else None
        opp = build_strategy_opportunity(pred, markets, strat, poisson_result=target_probs)
        if opp is None:
            row.update({"verdict": "SKIP", "reason": "warmup / filtro Bayes",
                        "model_prob": _f(pk["model_prob"]), "market_prob": None,
                        "edge": None, "stake": 0.0})
            rows.append(row)
            continue

        verdict = evaluate(opp, strat, portfolio)
        sizing = size_single(verdict, strat)
        stake = 0.0 if (verdict.verdict.value == "DISCARD" or sizing.skipped) else float(sizing.size_usdc)
        reason = (verdict.reasons[0] if verdict.reasons
                  else (verdict.blocking_rules[0] if verdict.blocking_rules else ""))
        row.update({
            "verdict": verdict.verdict.value,
            "reason": reason,
            "model_prob": _f(opp.model_probability),
            "market_prob": _f(opp.market_probability),
            "edge": _f(opp.edge),
            "stake": stake,
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
