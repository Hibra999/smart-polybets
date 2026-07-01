"""TradeIntent — intención de trade antes de validar precio live y construir orden."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from core.types import OrderSide


class TradeIntent(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition_id: str
    token_id: str
    outcome: str
    side: OrderSide
    size_usdc: Decimal
    signal_price: Decimal       # precio en la señal (de research)
