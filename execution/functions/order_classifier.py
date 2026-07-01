"""Clasificación final AUTO vs REVIEW de una orden. Función pura.

Es la última compuerta antes de enviar: si el verdict de Risk fue REVIEW, la
orden requiere aprobación humana (requires_approval=True) y NUNCA se envía sin ella.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from core.types import VerdictType
from core.utils import utcnow
from execution.schemas.execution_decision import ExecutionDecision
from execution.schemas.trade_order import TradeOrder
from risk.schemas.risk_verdict import RiskVerdict


def classify(
    order: TradeOrder,
    verdict: RiskVerdict,
    *,
    now: datetime | None = None,
    approval_buffer_hours: float = 1.0,
) -> ExecutionDecision:
    requires_approval = verdict.verdict == VerdictType.REVIEW
    opp = verdict.opportunity

    deadline = None
    if requires_approval:
        # Deadline = kickoff menos un buffer (no aprobar a último minuto).
        deadline = opp.event_start_utc - timedelta(hours=approval_buffer_hours)

    return ExecutionDecision(
        verdict=verdict,
        order_type=order.order_type.value,
        limit_price=order.price if order.order_type.value == "LIMIT" else None,
        size_usdc=order.size_usdc,
        polymarket_condition_id=order.condition_id,
        polymarket_token_id=order.token_id,
        side=order.side.value,
        idempotency_key=opp.idempotency_key,
        requires_approval=requires_approval,
        approval_deadline=deadline,
        created_at=now or utcnow(),
    )
