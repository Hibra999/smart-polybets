"""RiskVerdict — output de Risk hacia Execution.

VerdictType se define en core/types.py (single source of truth) y se re-exporta
aquí por fidelidad al whitepaper (que lo ubica junto al RiskVerdict).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from core.types import VerdictType  # re-export
from research.schemas.market_opportunity import MarketOpportunity

__all__ = ["RiskVerdict", "VerdictType"]


class RiskVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)

    opportunity: MarketOpportunity       # referencia al input
    verdict: VerdictType
    reasons: list[str] = Field(default_factory=list)        # razones en lenguaje natural
    kelly_fraction: Decimal              # fracción Kelly calculada
    recommended_size_usdc: Decimal       # tamaño recomendado
    blocking_rules: list[str] = Field(default_factory=list)  # reglas que bloquearon (si DISCARD)
    qualitative_flags: list[str] = Field(default_factory=list)  # QR-XXX que aplican
    evaluated_at: datetime

    @property
    def requires_approval(self) -> bool:
        return self.verdict == VerdictType.REVIEW
