#!/usr/bin/env python
"""Ingesta de fixtures para fifa_world_cup_2026 (API-Football.com).

STUB: define el punto de entrada de ingesta. El wiring real consulta API-Football
y hace UPSERT en la tabla `fixture` del SQLite, registrando en `ingest_log`.
Ver DATA_SOURCES.md para el contrato de la fuente.
"""
from __future__ import annotations

TOURNAMENT_ID = "fifa_world_cup_2026"
SOURCE = "api_football"
ENTITY = "fixture"


def run() -> None:
    print(f"[STUB] ingesta {ENTITY} para {TOURNAMENT_ID} desde {SOURCE}.")
    print("TODO: conectar API-Football, UPSERT en fixture, registrar en ingest_log.")


if __name__ == "__main__":
    run()
