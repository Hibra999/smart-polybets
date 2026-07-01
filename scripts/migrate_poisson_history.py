#!/usr/bin/env python
"""Puebla `historical_match` en el SQLite del torneo con histórico real de goles.

El modelo Poisson (adapters/football/wc_poisson) necesita partidos reales para
estimar ataque/defensa por equipo. El torneo en curso tiene pocos jugados, así que
se agrega Qatar 2022 (48 partidos, torneo completo) como referencia estática.

Fuente: worldcup.db (tournament_id=1, kind='backtest'). Los partidos del 2026 NO se
migran aquí: ya viven en `fixture` (status='finished') y los lee el pipeline; así se
evita doble conteo.

Mapea los team_id enteros del origen a nuestros slugs por nombre canónico. Equipos
2022 que no están en el field 2026 (Dinamarca, etc.) se guardan con su slug
derivado: aportan a la media de la liga aunque no se prediga sobre ellos.

Idempotente: DROP + CREATE + INSERT.

    python scripts/migrate_poisson_history.py
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = REPO_ROOT.parent / "pypro_worldcup_betting" / "app" / "data" / "worldcup.db"
TARGET_DB = REPO_ROOT / "data" / "fifa_world_cup_2026" / "fifa_world_cup_2026.sqlite"
SRC_TOURNAMENT_ID = 1  # Qatar 2022

DDL = """
CREATE TABLE IF NOT EXISTS historical_match (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    match_date    TEXT NOT NULL,
    home_team_id  TEXT NOT NULL,
    away_team_id  TEXT NOT NULL,
    home_goals    INTEGER NOT NULL,
    away_goals    INTEGER NOT NULL
);
"""


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")


def run(source: Path, target: Path) -> None:
    src = sqlite3.connect(source)
    names = {row[0]: row[1] for row in src.execute("SELECT id, name FROM team")}
    rows = src.execute(
        "SELECT date, home_team_id, away_team_id, home_goals, away_goals "
        "FROM match WHERE tournament_id=? AND home_goals IS NOT NULL "
        "AND away_goals IS NOT NULL ORDER BY date",
        (SRC_TOURNAMENT_ID,),
    ).fetchall()
    src.close()

    payload = [
        ("qatar_2022", d, slug(names.get(h, str(h))), slug(names.get(a, str(a))), hg, ag)
        for (d, h, a, hg, ag) in rows
    ]

    dst = sqlite3.connect(target)
    dst.execute("DROP TABLE IF EXISTS historical_match")
    dst.executescript(DDL)
    dst.executemany(
        "INSERT INTO historical_match "
        "(source, match_date, home_team_id, away_team_id, home_goals, away_goals) "
        "VALUES (?,?,?,?,?,?)",
        payload,
    )
    dst.commit()
    teams = dst.execute(
        "SELECT count(DISTINCT t) FROM ("
        "SELECT home_team_id t FROM historical_match "
        "UNION SELECT away_team_id FROM historical_match)"
    ).fetchone()[0]
    avg = dst.execute(
        "SELECT avg(home_goals + away_goals) FROM historical_match"
    ).fetchone()[0]
    dst.close()
    print(f"historical_match: {len(payload)} partidos, {teams} equipos, "
          f"avg {avg:.2f} goles/partido -> {target}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--target", type=Path, default=TARGET_DB)
    a = ap.parse_args()
    run(a.source, a.target)


if __name__ == "__main__":
    main()
