"""Schemas de la cuenta live de Polymarket (wallet + CLOB). Frozen."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AccountBalance(BaseModel):
    model_config = ConfigDict(frozen=True)

    usdc_balance: Decimal          # colateral pUSD disponible
    as_of: datetime
    address: str | None = None


class LivePosition(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition_id: str
    token_id: str
    outcome: str
    size_shares: Decimal
    avg_entry_price: Decimal        # precio medio de entrada (0-1)
    current_price: Decimal | None = None   # best_bid live (valor de salida)
    event_id: str | None = None
    tournament_id: str | None = None
    strategy_id: str | None = None

    @property
    def unrealized_pnl(self) -> Decimal | None:
        if self.current_price is None:
            return None
        return (self.current_price - self.avg_entry_price) * self.size_shares

    @property
    def market_value(self) -> Decimal | None:
        if self.current_price is None:
            return None
        return self.current_price * self.size_shares


class OpenOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    condition_id: str
    token_id: str
    side: str                       # "BUY" | "SELL"
    price: Decimal
    size_shares: Decimal
    size_matched: Decimal = Decimal("0")
    status: str = "open"
    created_at: datetime | None = None
    event_id: str | None = None
    tournament_id: str | None = None
    strategy_id: str | None = None
