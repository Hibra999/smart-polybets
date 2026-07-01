"""Config de adapter para FIFA World Cup 2026. Apunta a data/fifa_world_cup_2026/."""
from __future__ import annotations

TOURNAMENT_ID = "fifa_world_cup_2026"
SPORT = "football"


def build_adapter():
    from tournaments.registry import get_adapter
    return get_adapter(TOURNAMENT_ID)
