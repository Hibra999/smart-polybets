"""ResearchReport — agregado de oportunidades de un escaneo (output de quick_scan)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from research.schemas.market_opportunity import MarketOpportunity


class ResearchReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    tournament_ids: list[str] = Field(default_factory=list)
    opportunities: list[MarketOpportunity] = Field(default_factory=list)
    scanned_events: int = 0
    notes: list[str] = Field(default_factory=list)

    @property
    def top_by_edge(self) -> list[MarketOpportunity]:
        return sorted(self.opportunities, key=lambda o: o.edge, reverse=True)
