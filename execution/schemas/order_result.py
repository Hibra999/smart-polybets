"""OrderResult — respuesta del CLOB API tras enviar una orden."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class OrderResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    status: str                  # "filled" | "partial" | "open" | "rejected" | "stubbed"
    filled_size_usdc: Decimal
    avg_price: Decimal | None
    tx_hash: str | None = None
    submitted_at: datetime
    raw: dict = Field(default_factory=dict)  # respuesta cruda del API (auditoría)

    @property
    def is_filled(self) -> bool:
        return self.status in {"filled", "partial"}
