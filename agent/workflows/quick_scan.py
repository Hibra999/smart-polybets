"""Workflow: Quick Market Scan.

Status: approved
Trigger: cada 30 min durante un torneo activo (H-002)
Input: ninguno (detecta torneos activos desde LocalState)
Output: lista de MarketOpportunity ordenadas por edge desc

Para testear sin red/DB se puede inyectar `active_tournaments`,
`event_ids_by_tournament` y `market_source`.
"""
from __future__ import annotations

from collections.abc import Callable

from agent.tools import research_tools
from core.local_state import LocalStateClient
from research.schemas.market_opportunity import MarketOpportunity
from tournaments.registry import get_adapter, load_active_strategy


def _client(c: LocalStateClient | None) -> LocalStateClient:
    return c or LocalStateClient()


def _upcoming_event_ids(tournament_id: str, hours_ahead: int) -> list[str]:
    """IDs de eventos próximos del torneo, leídos del adapter (football/NFL)."""
    adapter = get_adapter(tournament_id)
    reader = getattr(adapter, "reader", None)
    if reader is None:
        return []
    if hasattr(reader, "get_upcoming_fixtures"):
        rows = reader.get_upcoming_fixtures(hours_ahead)
    elif hasattr(reader, "get_upcoming_games"):
        rows = reader.get_upcoming_games(hours_ahead)
    else:
        return []
    return [r["id"] for r in rows]


def run(
    *,
    client: LocalStateClient | None = None,
    active_tournaments: list[dict] | None = None,
    event_ids_by_tournament: dict[str, list[str]] | None = None,
    market_source: Callable | None = None,
    hours_ahead: int = 24,
    allow_draft: bool = False,
) -> list[MarketOpportunity]:
    tournaments = active_tournaments
    if tournaments is None:
        tournaments = _client(client).get_active_tournaments()

    all_opps: list[MarketOpportunity] = []
    for t in tournaments:
        tid = t["tournament_id"] if isinstance(t, dict) else t
        strategy = load_active_strategy(tid, require_approved=not allow_draft)
        if strategy is None:
            continue
        if event_ids_by_tournament is not None:
            event_ids = event_ids_by_tournament.get(tid, [])
        else:
            event_ids = _upcoming_event_ids(tid, hours_ahead)
        for event_id in event_ids:
            all_opps.extend(
                research_tools.scan_event(
                    event_id, tid, strategy, market_source=market_source
                )
            )

    return sorted(all_opps, key=lambda o: o.edge, reverse=True)
