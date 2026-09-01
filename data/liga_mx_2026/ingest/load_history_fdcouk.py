#!/usr/bin/env python
"""Carga la historia de Liga MX (football-data.co.uk) al SQLite del torneo.

Dos escrituras, ambas idempotentes:
  1. `historical_match` (para el Poisson): la temporada 2025/26 completa
     (Apertura 2025 + Clausura 2026, 336 partidos). Mazatlán entra como
     'mazatlan' — Atlante (su reemplazo en el Apertura 2026) NO hereda su
     historia: arranca en media de liga (decisión documentada; son clubes
     distintos aunque compartan franquicia).
  2. `team.elo_rating` (seeds): replay Elo (k=40, margin, home_adv del registry
     = 80 calibrado) sobre 2023/24 → 2025/26, con **regresión parcial a la media
     (ρ=0.80) en cada frontera Apertura/Clausura** — los torneos cortos reinician
     la TABLA pero no la fuerza; el grid conjunto (adv×ρ) dio óptimo en 80/0.80
     (Brier 0.15856 vs 0.15940 continuo; reset total empeora). Al final se aplica
     una regresión más (frontera Clausura 2026 → Apertura 2026) porque los seeds
     son PARA el torneo nuevo. Atlante queda en 1500 (media).

Fuente: MEX.csv (descargar/refrescar con:
  curl -sL -o data/liga_mx_2026/ingest/MEX.csv https://www.football-data.co.uk/new/MEX.csv)

    python data/liga_mx_2026/ingest/load_history_fdcouk.py            # dry-run
    python data/liga_mx_2026/ingest/load_history_fdcouk.py --apply
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.console import enable_utf8

enable_utf8()

from adapters.football.strength_models import EloSystem
from scripts.ligamx_backtest import load_matches  # mapping + parsing compartidos
from tournaments.registry import get_config

TID = "liga_mx_2026"
DB = REPO_ROOT / "data" / TID / f"{TID}.sqlite"
SOURCE = "fdcouk_2025_26"
POISSON_SEASONS = {"2025/2026"}
ELO_SEASONS = {"2023/2024", "2024/2025", "2025/2026"}
RHO = 0.80  # regresión a la media en fronteras de torneo corto (calibrado, ver docstring)


def torneo_corto(d) -> tuple[int, str]:
    """(año, 'A'|'C'): Jul-Dic = Apertura, Ene-Jun = Clausura."""
    return (d.year, "A" if d.month >= 7 else "C")


def regress(ratings: dict[str, float], rho: float = RHO) -> dict[str, float]:
    return {k: 1500.0 + rho * (v - 1500.0) for k, v in ratings.items()}

DDL = """
CREATE TABLE IF NOT EXISTS historical_match (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,
    match_date    TEXT NOT NULL,
    home_team_id  TEXT NOT NULL,
    away_team_id  TEXT NOT NULL,
    home_goals    INTEGER NOT NULL,
    away_goals    INTEGER NOT NULL
)
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    hist = load_matches(POISSON_SEASONS)
    elo_matches = load_matches(ELO_SEASONS)
    home_adv = get_config(TID).home_adv_elo

    elo = EloSystem(k=40.0, home_adv=home_adv)
    current = None
    for m in elo_matches:
        t = torneo_corto(m["date"])
        if current is not None and t != current:
            elo.ratings = regress(elo.ratings)
        current = t
        elo.update_match(m["home"], m["away"], m["hg"], m["ag"])
    # los seeds son PARA el Apertura 2026: una regresión más por la frontera
    # Clausura 2026 → Apertura 2026 (mercado de fichajes de verano).
    elo.ratings = regress(elo.ratings)

    con = sqlite3.connect(DB)
    con.execute(DDL)
    teams = {r[0] for r in con.execute("SELECT id FROM team WHERE tournament_id=?", (TID,))}

    print(f"=== load_history_fdcouk ({'APPLY' if a.apply else 'dry-run'}) ===")
    print(f"  historical_match: {len(hist)} partidos 2025/26 (source={SOURCE})")
    print(f"  Elo replay: {len(elo_matches)} partidos 2023/24-2025/26, home_adv={home_adv:.0f}\n")

    con.execute("DELETE FROM historical_match WHERE source=?", (SOURCE,))
    con.executemany(
        "INSERT INTO historical_match(source, match_date, home_team_id, away_team_id, "
        "home_goals, away_goals) VALUES(?,?,?,?,?,?)",
        [(SOURCE, m["date"].strftime("%Y-%m-%d"), m["home"], m["away"], m["hg"], m["ag"])
         for m in hist],
    )

    seeded = 0
    for team in sorted(teams):
        if team in elo.ratings:
            con.execute("UPDATE team SET elo_rating=? WHERE id=? AND tournament_id=?",
                        (round(elo.ratings[team], 1), team, TID))
            seeded += 1
            print(f"  seed {team:20s} elo={elo.ratings[team]:7.1f}")
        else:
            print(f"  seed {team:20s} SIN historia -> queda 1500.0 (media)")

    if a.apply:
        con.commit()
        print(f"\n[APLICADO] {len(hist)} historical_match · {seeded}/{len(teams)} seeds Elo")
    else:
        con.rollback()
        print("\n[DRY-RUN] rollback — nada escrito. Aplicar con --apply")
    con.close()


if __name__ == "__main__":
    main()
