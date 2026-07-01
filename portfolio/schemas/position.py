"""Position — una posición abierta en el portafolio (espejo del Django App)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class Position(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition_id: str
    token_id: str
    outcome: str
    tournament_id: str
    participant: str            # equipo/jugador al que está expuesta la posición

    size_usdc: Decimal          # capital comprometido
    entry_price: Decimal        # precio de entrada (0-1)
    current_price: Decimal      # precio live (0-1)
    shares: Decimal             # cantidad de shares

    opened_at: datetime

    @property
    def unrealized_pnl(self) -> Decimal:
        """PnL no realizado = (precio_actual - precio_entrada) * shares."""
        return (self.current_price - self.entry_price) * self.shares
