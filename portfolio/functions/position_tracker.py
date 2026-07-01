"""Puente con el Django App para estado e idempotencia.

Estas funciones NO son puras: son el rol explícito de portfolio/ como puente al
Django App (única fuente de estado). Reciben un DjangoClient por inyección para
mantenerse testeables (mock del cliente).

Regla: NUNCA cachear PortfolioState entre steps — siempre GET fresco.
"""
from __future__ import annotations

from typing import Any

from core.django_client import DjangoClient
from execution.schemas.execution_decision import ExecutionDecision
from execution.schemas.order_result import OrderResult
from portfolio.schemas.portfolio_state import PortfolioState


def get_state(client: DjangoClient) -> PortfolioState:
    """Lee el estado completo del portafolio (fresco) desde el Django App."""
    return PortfolioState.from_api(client.get_portfolio_state())


def get_exposure(client: DjangoClient, tournament_id: str) -> dict[str, Any]:
    """Exposición por participante del torneo (para el constraint de risk)."""
    return client.get_exposure_by_participant(tournament_id)


def check_idempotency(client: DjangoClient, idempotency_key: str) -> dict | None:
    """Retorna el DecisionLog existente o None. OBLIGATORIO antes de save_decision."""
    return client.check_idempotency(idempotency_key)


def save_decision(client: DjangoClient, decision: ExecutionDecision) -> dict:
    """Persiste un AgentDecisionLog. El Django valida la idempotency_key."""
    payload = _decision_payload(decision)
    return client.save_decision(payload)


def mark_executed(
    client: DjangoClient, idempotency_key: str, order_result: OrderResult
) -> dict:
    """Marca un DecisionLog como ejecutado y linkea el trade."""
    return client.mark_executed(idempotency_key, order_result.model_dump(mode="json"))


def _decision_payload(decision: ExecutionDecision) -> dict[str, Any]:
    """Serializa ExecutionDecision al contrato que espera POST /decisions/."""
    verdict = decision.verdict
    opp = verdict.opportunity
    # Equipo al que apunta la apuesta (para asentar PnL sin ambigüedad en el ledger).
    pick_participant = None
    if opp.model_outcome == "HOME_WIN":
        pick_participant = opp.participant_home
    elif opp.model_outcome == "AWAY_WIN":
        pick_participant = opp.participant_away
    return {
        "idempotency_key": decision.idempotency_key,
        "tournament_id": opp.tournament_id,
        "sport": opp.sport,
        "strategy_id": opp.strategy_id,
        "strategy_version": opp.strategy_version,
        "condition_id": decision.polymarket_condition_id,
        "outcome": opp.outcome,
        "pick_side": opp.model_outcome,
        "pick_participant": pick_participant,
        "verdict": verdict.verdict.value,
        "recommended_size": str(decision.size_usdc),
        "edge": str(opp.edge),
        "status": "pending_approval" if decision.requires_approval else "approved",
        "opportunity_json": opp.model_dump(mode="json"),
        "risk_verdict_json": verdict.model_dump(mode="json"),
    }
