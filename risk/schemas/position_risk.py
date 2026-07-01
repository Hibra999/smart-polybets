"""PositionRisk — métricas de riesgo de una posición candidata vs el portafolio."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PositionRisk(BaseModel):
    model_config = ConfigDict(frozen=True)

    participant: str
    current_exposure_pct: Decimal      # exposición actual al participante
    projected_exposure_pct: Decimal    # exposición si se abre esta posición
    correlation_estimate: float        # correlación con posiciones abiertas [0,1]
    within_exposure_limit: bool
    within_position_count_limit: bool
    within_drawdown_limit: bool

    @property
    def within_all_limits(self) -> bool:
        return (
            self.within_exposure_limit
            and self.within_position_count_limit
            and self.within_drawdown_limit
        )
