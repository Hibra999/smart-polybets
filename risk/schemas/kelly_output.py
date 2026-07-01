"""KellyOutput — resultado del cálculo de Kelly fraccional."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class KellyOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw_kelly: Decimal          # fracción Kelly completa (sin escalar)
    kelly_fraction: Decimal     # fracción aplicada = raw_kelly * fraction_multiplier
    fraction_multiplier: Decimal  # ej: 0.25 (quarter-Kelly)
    recommended_size_usdc: Decimal
    bankroll_usdc: Decimal
    capped: bool = False        # True si se topó a max_bet_usdc o max_kelly_fraction
    notes: list[str] = []
