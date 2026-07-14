"""Config de adapter para Liga MX Apertura 2026. Apunta a data/liga_mx_2026/."""
from __future__ import annotations

TOURNAMENT_ID = "liga_mx_2026"
SPORT = "football"


def build_adapter():
    from tournaments.registry import get_adapter
    return get_adapter(TOURNAMENT_ID)
