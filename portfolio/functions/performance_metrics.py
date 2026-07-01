"""Métricas de performance del portafolio. Función pura."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from core.utils import to_decimal, utcnow
from portfolio.functions.pnl_calculator import realized_pnl, unrealized_pnl
from portfolio.schemas.performance_summary import PerformanceSummary
from portfolio.schemas.portfolio_state import PortfolioState


def summary(
    portfolio_state: PortfolioState,
    resolved_trades: list[dict[str, Any]] | None = None,
    *,
    tournament_id: str | None = None,
    max_drawdown: Decimal | float | None = None,
) -> PerformanceSummary:
    trades = resolved_trades or []
    wins = sum(1 for t in trades if t.get("won"))
    losses = sum(1 for t in trades if t.get("won") is False)
    realized = realized_pnl(trades)
    unrealized = unrealized_pnl(portfolio_state.open_positions)

    return PerformanceSummary(
        tournament_id=tournament_id,
        as_of=utcnow(),
        bankroll_usdc=portfolio_state.bankroll_usdc,
        pnl_realized=realized,
        pnl_unrealized=unrealized,
        total_trades=len(trades),
        wins=wins,
        losses=losses,
        drawdown_current=portfolio_state.drawdown_7d,
        drawdown_max=to_decimal(max_drawdown) if max_drawdown is not None
        else portfolio_state.drawdown_7d,
    )
