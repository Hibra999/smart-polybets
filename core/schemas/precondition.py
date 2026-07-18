"""Resultado de una precondición de datos. Frozen. Ver
docs/superpowers/specs/2026-07-17-mandatory-dependency-hooks-design.md."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class PreconditionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    ok: bool | None                       # True=cumple, False=viola, None=no verificable
    severity: Literal["mandatory", "advisory"]
    tournament_id: str | None = None
    detail: str = ""
    remedy_cmd: str | None = None

    @property
    def is_violation(self) -> bool:
        return self.severity == "mandatory" and self.ok is False
