#!/usr/bin/env python
"""Ingesta del calendario NFL para nfl_2026 (ESPN / nflverse schedule).

STUB: el wiring real puebla `week` y `fixture` (incluye líneas de Vegas si la
fuente de odds está disponible).
"""
from __future__ import annotations

TOURNAMENT_ID = "nfl_2026"
SOURCE = "nflverse"
ENTITY = "fixture"


def run() -> None:
    print(f"[STUB] ingesta {ENTITY}/week para {TOURNAMENT_ID} desde {SOURCE}.")
    print("TODO: UPSERT week + fixture (spread/total/moneyline desde odds API).")


if __name__ == "__main__":
    run()
