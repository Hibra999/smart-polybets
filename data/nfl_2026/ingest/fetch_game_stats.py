#!/usr/bin/env python
"""Ingesta de estadísticas post-partido NFL para nfl_2026 (nflverse).

STUB: el wiring real puebla `match_team_stat` y `match_player_stat`, y dispara el
recálculo de Elo (elo_rating_history).
"""
from __future__ import annotations

TOURNAMENT_ID = "nfl_2026"
SOURCE = "nflverse"
ENTITY = "match_team_stat"


def run() -> None:
    print(f"[STUB] ingesta {ENTITY}/match_player_stat para {TOURNAMENT_ID}.")
    print("TODO: UPSERT stats + recálculo de elo_rating_history.")


if __name__ == "__main__":
    run()
