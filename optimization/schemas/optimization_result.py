"""OptimizationResult — resultado de optimizar un batch de oportunidades."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from optimization.schemas.sizing_output import SizingOutput


class OptimizationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    # idempotency_key -> SizingOutput
    allocations: dict[str, SizingOutput] = Field(default_factory=dict)
    objective_value: Decimal | None = None  # EV esperado del batch
    converged: bool = True
    method: str = "cvxpy_batch"             # o "fallback_kelly" si cvxpy no convergió
    notes: list[str] = Field(default_factory=list)
