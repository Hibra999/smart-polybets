"""Cálculo de PnL. Funciones puras."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.utils import to_decimal
from portfolio.schemas.position import Position


def realized_pnl(trades: list[dict[str, Any]]) -> Decimal:
    """PnL realizado acumulado de trades resueltos (cada trade tiene `pnl`)."""
    return sum((to_decimal(t.get("pnl", 0)) for t in trades), Decimal("0"))


def unrealized_pnl(positions: list[Position]) -> Decimal:
    """PnL no realizado de posiciones abiertas."""
    return sum((p.unrealized_pnl for p in positions), Decimal("0"))
