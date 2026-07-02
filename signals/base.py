from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class Signal(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_probability: Decimal
    side: str  # "HOME_WIN" | "AWAY_WIN"
    model_confidence: str
    model_version: str
    sample_size: int


class SignalProvider(Protocol):
    sport: str

    def signal(self, home: str, away: str, *, event_id: str | None = None) -> "Signal | None":
        ...
