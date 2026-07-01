#!/usr/bin/env python
"""Ingesta de rosters + injury report NFL para nfl_2026 (nflverse).

STUB: el wiring real puebla `player` y `injury_report` (el injury report sale los
jueves y es crítico para QR-201).
"""
from __future__ import annotations

TOURNAMENT_ID = "nfl_2026"
SOURCE = "nflverse"
ENTITY = "player"


def run() -> None:
    print(f"[STUB] ingesta {ENTITY} + injury_report para {TOURNAMENT_ID}.")
    print("TODO: UPSERT player + injury_report (status de QBs titulares).")


if __name__ == "__main__":
    run()
