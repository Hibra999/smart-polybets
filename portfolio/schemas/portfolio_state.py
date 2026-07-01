"""PortfolioState — snapshot del portafolio leído del Django App.

Consumido por risk/ y optimization/. NUNCA se cachea entre steps del pipeline:
siempre se obtiene fresco vía position_tracker.get_state().
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from portfolio.schemas.position import Position


class PortfolioState(BaseModel):
    model_config = ConfigDict(frozen=True)

    bankroll_usdc: Decimal
    drawdown_7d: Decimal                 # fracción [0,1]
    open_positions: list[Position] = Field(default_factory=list)
    exposure_by_participant: dict[str, Decimal] = Field(default_factory=dict)
    as_of: datetime

    @property
    def total_open_positions(self) -> int:
        return len(self.open_positions)

    def exposure_for(self, participant: str) -> Decimal:
        """Exposición actual (fracción del bankroll) al participante."""
        return self.exposure_by_participant.get(participant, Decimal("0"))

    @classmethod
    def from_api(cls, payload: dict) -> "PortfolioState":
        """Construye desde la respuesta del Django App (/portfolio/state/)."""
        positions = [Position(**p) for p in payload.get("open_positions", [])]
        return cls(
            bankroll_usdc=Decimal(str(payload["bankroll_usdc"])),
            drawdown_7d=Decimal(str(payload.get("drawdown_7d", "0"))),
            open_positions=positions,
            exposure_by_participant={
                k: Decimal(str(v))
                for k, v in payload.get("exposure_by_participant", {}).items()
            },
            as_of=payload.get("as_of") or datetime.now().astimezone(),
        )
