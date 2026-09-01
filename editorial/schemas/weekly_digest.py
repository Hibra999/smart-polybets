"""WeeklyDigest — digest de performance de un período (whitepaper sección 15)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from editorial.schemas.trade_report import TradeReport


class WeeklyDigest(BaseModel):
    model_config = ConfigDict(frozen=True)

    period_start: datetime
    period_end: datetime
    tournament_id: str | None = None

    # Performance
    total_bets: int
    auto_bets: int
    review_bets: int
    approved_reviews: int
    rejected_reviews: int
    discarded: int

    pnl_realized: Decimal
    pnl_unrealized: Decimal
    win_rate: float
    roi: float

    # Edge analysis
    avg_edge_at_entry: Decimal
    avg_edge_captured: Decimal     # edge real vs edge predicho
    edge_accuracy: float           # % veces que edge > 0 fue correcto

    # Best/worst
    best_trade: TradeReport | None = None
    worst_trade: TradeReport | None = None

    # Narrativa generada por Codex
    performance_narrative: str = ""
    lessons_learned: list[str] = Field(default_factory=list)
    next_week_outlook: str = ""
