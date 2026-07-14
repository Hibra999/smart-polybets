"""Workflow: Full Event Analysis.

Status: approved
Trigger: manual o Celery task pre-evento (H-001)
Input: event_id, tournament_id
Output: lista de decisiones (AUTO / REVIEW / DISCARD / SKIP)

Pipeline (orden reconciliado con los SKILL.md):
  Research → Risk → Optimization → Execution → Portfolio (+ Editorial si REVIEW)

Recibe `client` y `market_source` por inyección para ser testeable sin red.
"""
from __future__ import annotations

from typing import Callable

from decimal import Decimal

from core.local_state import LocalStateClient
from core.exceptions import NoActiveStrategyError
from agent.tools import execution_tools, portfolio_tools, research_tools, risk_tools
from editorial.functions import build_execution_summary, build_review_report
from execution.functions import PolymarketBroker, validate_live_price
from optimization.functions import size_single
from tournaments.registry import load_active_strategy


def run(
    event_id: str,
    tournament_id: str,
    *,
    client: LocalStateClient | None = None,
    market_source: Callable | None = None,
    qualitative_flags: list[str] | None = None,
    broker: PolymarketBroker | None = None,
    price_tolerance: Decimal = Decimal("0.15"),
) -> list[dict]:
    strategy = load_active_strategy(tournament_id)
    if strategy is None:
        raise NoActiveStrategyError(f"No hay estrategia aprobada para {tournament_id}")

    # Estado fresco al inicio del pipeline.
    portfolio_state = portfolio_tools.get_state(client)

    opportunities = research_tools.scan_event(
        event_id, tournament_id, strategy, market_source=market_source
    )

    decisions: list[dict] = []
    for opp in opportunities:
        key = opp.idempotency_key

        # 1. Idempotencia — OBLIGATORIA antes de procesar. `simulated` (dry-run
        # previo) y `expired` NO bloquean: el run real puede reprocesarlas.
        existing = portfolio_tools.check_idempotency(key, client)
        if existing is not None and existing.get("status") not in ("expired", "simulated"):
            decisions.append({"mode": "SKIP", "idempotency_key": key, "reason": "ya procesada"})
            continue

        # 2. Risk
        verdict = risk_tools.evaluate(
            opp, strategy, portfolio_state, qualitative_flags=qualitative_flags
        )

        if verdict.verdict.value == "DISCARD":
            decisions.append(
                {"mode": "DISCARD", "idempotency_key": key, "reasons": verdict.reasons}
            )
            continue

        # 3. Optimization (refina el tamaño)
        sizing = size_single(verdict, strategy)
        if sizing.skipped:
            decisions.append(
                {"mode": "SKIP", "idempotency_key": key, "reason": "; ".join(sizing.notes)}
            )
            continue

        # 4. Execution — orden al best_ask live (precio real de compra).
        order = execution_tools.build_order(verdict, sizing)
        decision = execution_tools.classify_order(order, verdict)

        # 5. Portfolio — persiste la decisión.
        portfolio_tools.save_decision(decision, client)

        if decision.requires_approval:
            decisions.append(
                {
                    "mode": "REVIEW",
                    "idempotency_key": key,
                    "report": build_review_report(decision),
                }
            )
        else:
            # Guarda de slippage: si el precio de ejecución (best_ask) se movió más
            # allá de la tolerancia vs la señal (mid), NO ejecutar — re-evaluar.
            if opp.best_ask is not None and not validate_live_price(
                opp.market_probability, opp.best_ask, price_tolerance
            ):
                decisions.append({
                    "mode": "SKIP", "idempotency_key": key,
                    "reason": f"precio live {opp.best_ask} se movió >{price_tolerance} vs señal {opp.market_probability}",
                })
                continue
            result = execution_tools.submit(order, decision, broker=broker)
            # Sólo un fill REAL marca ejecutado; un dry-run queda `simulated`
            # (no bloquea el run live siguiente). Paridad con orders.py.
            if result.status == "live":
                portfolio_tools.mark_executed(key, result, client)
            else:
                portfolio_tools.mark_simulated(key, result, client)
            decisions.append(
                {
                    "mode": "AUTO",
                    "idempotency_key": key,
                    "result": result.model_dump(mode="json"),
                    "summary": build_execution_summary(result, verdict),
                }
            )

    return decisions
