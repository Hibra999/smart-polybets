"""Workflow: Post Event Review.

Status: approved
Trigger: manual después de que resuelve un mercado (H-005)
Input: event_id, tournament_id
Output: dict con el digest y el path del reporte guardado

Compara la predicción del modelo vs el resultado real y guarda un reporte en
editorial/reports/{tournament_id}/.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.utils import utcnow
from editorial.functions import save_report
from editorial.functions.performance_digest import weekly
from tournaments.registry import get_adapter


def _fixture_result(tournament_id: str, event_id: str) -> dict[str, Any] | None:
    adapter = get_adapter(tournament_id)
    reader = getattr(adapter, "reader", None)
    if reader is None:
        return None
    if hasattr(reader, "get_fixture"):
        return reader.get_fixture(event_id)
    if hasattr(reader, "get_game"):
        return reader.get_game(event_id)
    return None


def run(
    event_id: str,
    tournament_id: str,
    *,
    decisions: list[dict] | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    save: bool = True,
) -> dict[str, Any]:
    result = _fixture_result(tournament_id, event_id)
    start = period_start or datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = period_end or utcnow()

    digest = weekly(tournament_id, start, end, decisions or [])

    lines = [
        f"# Post-Event Review — {tournament_id} / {event_id}",
        "",
        f"- Generado: {utcnow().isoformat()}",
        f"- Decisiones analizadas: {digest.total_bets} "
        f"(AUTO {digest.auto_bets}, REVIEW {digest.review_bets}, DISCARD {digest.discarded})",
        f"- PnL realizado: {digest.pnl_realized} USDC",
        f"- Edge promedio entrada: {digest.avg_edge_at_entry}",
    ]
    if result is not None:
        lines += [
            "",
            "## Resultado del evento",
            f"- Status: {result.get('status')}",
            f"- {result.get('home_team_name', result.get('home_team_id'))} "
            f"{result.get('home_goals', result.get('home_score', '-'))} - "
            f"{result.get('away_goals', result.get('away_score', '-'))} "
            f"{result.get('away_team_name', result.get('away_team_id'))}",
        ]
    content = "\n".join(lines) + "\n"

    path = None
    if save:
        path = save_report(tournament_id, content, suffix=f"{event_id}_review")

    return {"digest": digest, "report_path": str(path) if path else None, "report": content}
