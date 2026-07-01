"""Digests de performance (semanal y final de torneo). Función pura.

Recibe los datos ya agregados (decisiones/trades del período) y construye un
WeeklyDigest. La narrativa la expande Claude; aquí se computan los números.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from core.utils import to_decimal
from editorial.schemas.weekly_digest import WeeklyDigest


def _digest_from_records(
    period_start: datetime,
    period_end: datetime,
    decisions: list[dict[str, Any]],
    *,
    tournament_id: str | None,
) -> WeeklyDigest:
    def count(pred) -> int:
        return sum(1 for d in decisions if pred(d))

    total = len(decisions)
    auto = count(lambda d: d.get("verdict") == "AUTO")
    review = count(lambda d: d.get("verdict") == "REVIEW")
    approved = count(lambda d: d.get("status") == "approved")
    rejected = count(lambda d: d.get("status") == "rejected")
    discarded = count(lambda d: d.get("verdict") == "DISCARD" or d.get("status") == "discarded")

    realized = sum((to_decimal(d.get("pnl", 0)) for d in decisions), Decimal("0"))
    edges = [to_decimal(d.get("edge", 0)) for d in decisions if "edge" in d]
    avg_edge = (sum(edges, Decimal("0")) / len(edges)) if edges else Decimal("0")

    settled = [d for d in decisions if "won" in d]
    wins = sum(1 for d in settled if d.get("won"))
    win_rate = (wins / len(settled)) if settled else 0.0

    return WeeklyDigest(
        period_start=period_start,
        period_end=period_end,
        tournament_id=tournament_id,
        total_bets=total,
        auto_bets=auto,
        review_bets=review,
        approved_reviews=approved,
        rejected_reviews=rejected,
        discarded=discarded,
        pnl_realized=realized,
        pnl_unrealized=Decimal("0"),
        win_rate=win_rate,
        roi=0.0,
        avg_edge_at_entry=avg_edge,
        avg_edge_captured=Decimal("0"),
        edge_accuracy=0.0,
    )


def weekly(
    tournament_id: str,
    period_start: datetime,
    period_end: datetime,
    decisions: list[dict[str, Any]] | None = None,
) -> WeeklyDigest:
    return _digest_from_records(
        period_start, period_end, decisions or [], tournament_id=tournament_id
    )


def tournament_final(
    tournament_id: str,
    period_start: datetime,
    period_end: datetime,
    decisions: list[dict[str, Any]] | None = None,
) -> WeeklyDigest:
    digest = _digest_from_records(
        period_start, period_end, decisions or [], tournament_id=tournament_id
    )
    return digest
