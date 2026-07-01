#!/usr/bin/env python
"""Ingesta de planteles y disponibilidad para fifa_world_cup_2026.

STUB: el wiring real scrapea Transfermarkt (players) + fuentes de lesiones para
poblar `player` y `player_availability`.
"""
from __future__ import annotations

TOURNAMENT_ID = "fifa_world_cup_2026"
SOURCE = "transfermarkt"
ENTITY = "player"


def run() -> None:
    print(f"[STUB] ingesta {ENTITY} + player_availability para {TOURNAMENT_ID}.")
    print("TODO: scrape Transfermarkt, UPSERT en player/player_availability.")


if __name__ == "__main__":
    run()
