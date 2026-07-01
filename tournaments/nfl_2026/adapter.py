"""Config de adapter para NFL 2026. Apunta a data/nfl_2026/."""
from __future__ import annotations

TOURNAMENT_ID = "nfl_2026"
SPORT = "american_football"


def build_adapter():
    from tournaments.registry import get_adapter
    return get_adapter(TOURNAMENT_ID)
