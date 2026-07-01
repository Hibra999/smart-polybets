"""TradeReport — resumen estructurado de un trade (para digests y narrativas)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TradeReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition_id: str
    tournament_id: str
    participant_home: str
    participant_away: str
    outcome: str
    mode: str                    # "AUTO" | "REVIEW"

    edge_at_entry: Decimal
    size_usdc: Decimal
    entry_price: Decimal | None = None
    pnl: Decimal | None = None   # None si la posición sigue abierta

    executed_at: datetime | None = None
    narrative: str | None = None
