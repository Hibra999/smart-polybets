"""TradeOrder — payload listo para el CLOB API de Polymarket."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from core.types import OrderSide, OrderType


class TradeOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition_id: str
    token_id: str
    outcome: str
    side: OrderSide
    order_type: OrderType
    price: Decimal              # precio límite (para LIMIT) o precio de referencia
    size_usdc: Decimal
    size_shares: Decimal        # size_usdc / price
    tif: str = "GTC"            # time in force: GTC | FOK | IOC

    # Metadata de ejecución real (la llena order_builder desde el PolymarketMarket
    # live; opcional para órdenes construidas sin mercado live).
    neg_risk: bool = False
    tick_size: Decimal | None = None
    min_order_size: Decimal | None = None

    @property
    def is_marketable(self) -> bool:
        return self.order_type == OrderType.MARKET
