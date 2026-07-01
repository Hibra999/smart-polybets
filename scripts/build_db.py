#!/usr/bin/env python
"""Construye el SQLite de un torneo a partir del DDL canónico de su deporte.

Uso:
    python scripts/build_db.py --tournament fifa_world_cup_2026 --sport football
    python scripts/build_db.py --tournament nfl_2026 --sport american_football

Crea `data/{tournament_id}/{tournament_id}.sqlite` con el schema vacío. La
ingesta de datos reales es responsabilidad de los scripts en
`data/{tournament_id}/ingest/`.

GAP RESUELTO: el whitepaper menciona "un SQLite por torneo" pero no define el
builder. Este script materializa el DDL de `data/_schema/{sport}.sql`.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "data" / "_schema"
DATA_ROOT = REPO_ROOT / "data"


def build_db(tournament_id: str, sport: str, *, overwrite: bool = False) -> Path:
    schema_path = SCHEMA_DIR / f"{sport}.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"No existe DDL para el deporte {sport!r}: {schema_path}")

    out_dir = DATA_ROOT / tournament_id
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / f"{tournament_id}.sqlite"

    if db_path.exists():
        if not overwrite:
            raise FileExistsError(
                f"{db_path} ya existe. Usá --overwrite para reconstruir desde cero."
            )
        db_path.unlink()

    ddl = schema_path.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(ddl)
        conn.commit()
    finally:
        conn.close()
    return db_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Construye el SQLite de un torneo.")
    parser.add_argument("--tournament", required=True, help="tournament_id, ej: fifa_world_cup_2026")
    parser.add_argument(
        "--sport",
        required=True,
        choices=["football", "american_football"],
        help="deporte (determina el DDL canónico)",
    )
    parser.add_argument("--overwrite", action="store_true", help="reconstruir si ya existe")
    args = parser.parse_args()

    path = build_db(args.tournament, args.sport, overwrite=args.overwrite)
    print(f"[OK] SQLite creado: {path}")


if __name__ == "__main__":
    main()
