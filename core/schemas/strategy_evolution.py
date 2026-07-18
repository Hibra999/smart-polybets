"""Resultado del validador de evolución de estrategias. Frozen."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrategyEvolutionCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: str
    ok: bool
    detail: str = ""
    remedy_cmd: str | None = None
