#!/usr/bin/env python
"""Ingesta de estadísticas post-partido para fifa_world_cup_2026.

STUB: el wiring real consulta API-Football tras cada partido para poblar
`match_team_stat` y dispara el recálculo de Elo (elo_rating_history).
"""
from __future__ import annotations

TOURNAMENT_ID = "fifa_world_cup_2026"
SOURCE = "api_football"
ENTITY = "match_team_stat"


def run() -> None:
    print(f"[STUB] ingesta {ENTITY} para {TOURNAMENT_ID} desde {SOURCE}.")
    print("TODO: UPSERT match_team_stat + recálculo de elo_rating_history.")


if __name__ == "__main__":
    run()
