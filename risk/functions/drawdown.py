"""Drawdown / stop-loss de portafolio. Funciones puras."""
from __future__ import annotations

from decimal import Decimal

from core.utils import to_decimal
from portfolio.schemas.portfolio_state import PortfolioState


def check_portfolio_stop_loss(
    portfolio_state: PortfolioState, max_drawdown: Decimal | float
) -> bool:
    """True si el drawdown 7d SUPERA el límite (→ bloquear nuevas posiciones)."""
    return portfolio_state.drawdown_7d > to_decimal(max_drawdown)


def position_stop_loss_triggered(
    entry_value_usdc: Decimal | float,
    current_value_usdc: Decimal | float,
    stop_loss_pct: Decimal | float = Decimal("0.60"),
) -> bool:
    """True si la pérdida no realizada supera `stop_loss_pct` del valor inicial.

    Regla del STRATEGY.md: stop-loss por posición si pérdida unrealizada > 60%.
    """
    entry = to_decimal(entry_value_usdc)
    if entry <= 0:
        return False
    loss_frac = (entry - to_decimal(current_value_usdc)) / entry
    return loss_frac > to_decimal(stop_loss_pct)
