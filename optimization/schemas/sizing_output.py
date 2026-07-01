"""SizingOutput — tamaño final recomendado para una apuesta."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SizingOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    size_usdc: Decimal
    method: str                  # "fractional_kelly" | "cvxpy_batch" | "fallback_kelly"
    kelly_fraction: Decimal      # fracción del bankroll resultante
    skipped: bool = False        # True si size < min_bet_usdc → no operar
    capped_by: str | None = None  # "max_bet" | "max_kelly_fraction" | None
    notes: list[str] = Field(default_factory=list)
