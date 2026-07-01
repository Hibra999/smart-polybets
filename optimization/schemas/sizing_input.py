"""SizingInput — entrada para el cálculo de tamaño de una apuesta."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SizingInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    win_probability: Decimal     # probabilidad del modelo (0-1)
    price: Decimal               # precio del token YES (0-1) = prob implícita del mercado
    bankroll_usdc: Decimal
    kelly_fraction: Decimal      # multiplicador fraccional (ej: 0.25)
    max_bet_usdc: Decimal
    min_bet_usdc: Decimal
    max_kelly_fraction: Decimal = Decimal("0.05")  # cap de fracción del bankroll
