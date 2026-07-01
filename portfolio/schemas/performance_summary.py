"""PerformanceSummary — métricas agregadas de performance del portafolio."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PerformanceSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    tournament_id: str | None = None
    as_of: datetime

    bankroll_usdc: Decimal
    pnl_realized: Decimal
    pnl_unrealized: Decimal

    total_trades: int
    wins: int
    losses: int

    drawdown_current: Decimal
    drawdown_max: Decimal

    @property
    def win_rate(self) -> float:
        decided = self.wins + self.losses
        return (self.wins / decided) if decided else 0.0

    @property
    def roi(self) -> float:
        if self.bankroll_usdc == 0:
            return 0.0
        return float((self.pnl_realized + self.pnl_unrealized) / self.bankroll_usdc)
