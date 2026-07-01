"""ExecutionDecision — output de Execution hacia el Django App."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from risk.schemas.risk_verdict import RiskVerdict


class ExecutionDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: RiskVerdict               # referencia al input
    order_type: str                    # "MARKET" | "LIMIT"
    limit_price: Decimal | None        # si es LIMIT
    size_usdc: Decimal                 # tamaño final
    polymarket_condition_id: str
    polymarket_token_id: str
    side: str                          # "BUY" | "SELL"

    # Estado para idempotencia en Django
    idempotency_key: str               # hash(condition_id + outcome + generated_at)
    requires_approval: bool            # True si verdict == REVIEW
    approval_deadline: datetime | None  # para REVIEW: deadline antes del partido

    created_at: datetime
