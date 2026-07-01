"""Sizing de una sola apuesta.

Consume el RiskVerdict (que ya trae el Kelly calculado por Risk) y aplica los
constraints del STRATEGY.md: cap por max_bet_usdc y SKIP si cae por debajo de
min_bet_usdc. NO recalcula Kelly (eso es de Risk) y NUNCA modifica el verdict —
sólo el tamaño.
"""
from __future__ import annotations

from decimal import Decimal

from core.strategy import StrategyConfig
from core.utils import quantize_usdc
from optimization.schemas.sizing_output import SizingOutput
from risk.schemas.risk_verdict import RiskVerdict


def size_single(verdict: RiskVerdict, strategy: StrategyConfig) -> SizingOutput:
    size = verdict.recommended_size_usdc
    notes: list[str] = []
    capped_by: str | None = None

    if size > strategy.max_bet_usdc:
        size = strategy.max_bet_usdc
        capped_by = "max_bet"
        notes.append(f"topado a max_bet_usdc={strategy.max_bet_usdc}")

    if size < strategy.min_bet_usdc:
        notes.append(
            f"size {size} < min_bet_usdc {strategy.min_bet_usdc} → SKIP (no operar)"
        )
        return SizingOutput(
            size_usdc=Decimal("0"),
            method=strategy.sizing_method,
            kelly_fraction=verdict.kelly_fraction,
            skipped=True,
            capped_by=capped_by,
            notes=notes,
        )

    return SizingOutput(
        size_usdc=quantize_usdc(size),
        method=strategy.sizing_method,
        kelly_fraction=verdict.kelly_fraction,
        skipped=False,
        capped_by=capped_by,
        notes=notes,
    )
