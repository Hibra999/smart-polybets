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
    title: str | None = None        # nombre legible del mercado (del SDK live)
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


class ClosedPositionLive(BaseModel):
    """Posición ya cerrada/resuelta en la wallet (historial live). PnL realizado."""

    model_config = ConfigDict(frozen=True)

    condition_id: str
    token_id: str
    outcome: str
    avg_price: Decimal
    realized_pnl: Decimal
    current_price: Decimal | None = None
    closed_at: datetime | None = None
    title: str | None = None
    event_id: str | None = None


class LiveTrade(BaseModel):
    """Un fill on-chain de la wallet (compra o venta). Insumo del PnL por flujo de caja."""

    model_config = ConfigDict(frozen=True)

    side: str                       # "BUY" | "SELL"
    size_shares: Decimal
    price: Decimal                  # precio del fill (0-1)
    condition_id: str
    outcome: str | None = None
    title: str | None = None
    timestamp: datetime | None = None

    @property
    def usdc(self) -> Decimal:
        """USDC movido en el fill (shares × precio), siempre positivo."""
        return self.size_shares * self.price


class LiveRedemption(BaseModel):
    """Un evento REDEEM: cobro de un mercado resuelto (el payout en USDC)."""

    model_config = ConfigDict(frozen=True)

    condition_id: str
    amount: Decimal                 # USDC cobrado (0 si el lado redimido perdió)
    title: str | None = None
    timestamp: datetime | None = None


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
