#!/usr/bin/env python
"""Sincroniza los fixtures de eliminatorias pendientes con los partidos reales de
Polymarket (Gamma API).

La DB modela las eliminatorias con placeholders de bracket (group_c_winner, ...) y
horarios que no coinciden con la realidad. Una vez que Polymarket resuelve el bracket
y publica los partidos con equipos reales ("X vs. Y", "Will X win on YYYY-MM-DD?"),
este script trae esos partidos y reescribe los placeholders pendientes con:
  - home_team_id / away_team_id reales (mapeados con _canon → team_id del proyecto)
  - kickoff_utc real (gameStartTime del mercado)

Como la DB no almacena la pertenencia a grupos (no se puede resolver el bracket
localmente) y los datos son simulados, el mapeo placeholder→partido se hace por orden
de kickoff entre los placeholders pendientes (kickoff >= hoy) y los partidos abiertos
de Polymarket, que coinciden 1:1 para la ronda en curso.

Dry-run por defecto; --apply escribe (hace backup del .sqlite antes).

    python scripts/sync_upcoming_fixtures.py
    python scripts/sync_upcoming_fixtures.py --apply
"""
from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8
from venue.discovery import match_events
from venue.matching import canon as _canon

enable_utf8()

TID = "fifa_world_cup_2026"
REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / TID / f"{TID}.sqlite"
# placeholder de bracket basado en posición de grupo (fase de 32)
_GROUP_PH = re.compile(r"^group_[a-l]_(winner|2nd_place)$|^third_place_group", re.I)


def fetch_polymarket_matches() -> list[dict]:
    """[{home_canon, away_canon, home_disp, away_disp, kickoff}] ordenado por kickoff.

    Vía el helper unificado `venue.discovery.match_events` (SDK, sin scraper Gamma).
    """
    out = []
    for me in match_events(closed=False):
        if not me.has_winner_market or me.kickoff is None:
            continue
        out.append({
            "home_disp": me.home_disp, "away_disp": me.away_disp,
            "home_canon": me.home_canon, "away_canon": me.away_canon,
            "kickoff": me.kickoff.astimezone(timezone.utc).isoformat(),
        })
    out.sort(key=lambda x: x["kickoff"])
    return out


def run(apply: bool) -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    teams = {r["id"] for r in con.execute("SELECT id FROM team")}
    canon2db = {_canon(t.replace("_", " ")): t for t in teams}

    pm = fetch_polymarket_matches()
    # resolver a team_id del proyecto; descartar los que no mapean a 2 equipos conocidos
    resolved = []
    for g in pm:
        h = canon2db.get(g["home_canon"]); a = canon2db.get(g["away_canon"])
        if h and a:
            resolved.append({**g, "home_id": h, "away_id": a})

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    placeholders = con.execute(
        "SELECT id, kickoff_utc, home_team_id, away_team_id FROM fixture "
        "WHERE status='scheduled' AND kickoff_utc >= ? ORDER BY kickoff_utc",
        (today + "T00:00:00+00:00",),
    ).fetchall()
    pend = [r for r in placeholders
            if _GROUP_PH.match(r["home_team_id"]) or _GROUP_PH.match(r["away_team_id"])]

    print(f"Partidos reales en Polymarket (open, mapeados): {len(resolved)}")
    print(f"Placeholders de fase de 32 pendientes (kickoff >= {today}): {len(pend)}\n")

    n = min(len(resolved), len(pend))
    updates = []
    for i in range(n):
        row, match = pend[i], resolved[i]
        updates.append((row["id"], match["home_id"], match["away_id"], match["kickoff"]))
        print(f"  {row['id']:>7}  {row['home_team_id'][:22]:<22} vs {row['away_team_id'][:22]:<22}")
        print(f"          -> {match['home_id']:<16} vs {match['away_id']:<16}  "
              f"kickoff {match['kickoff'][:16]}  (PM: {match['home_disp']} vs {match['away_disp']})")

    if len(resolved) != len(pend):
        print(f"\n  [!] desajuste: {len(resolved)} partidos PM vs {len(pend)} placeholders; "
              f"se sincronizan los primeros {n} por orden de kickoff.")

    if apply and updates:
        bak = DB.with_suffix(f".sqlite.bak-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}")
        shutil.copy2(DB, bak)
        print(f"\n  backup: {bak.name}")
        con.executemany(
            "UPDATE fixture SET home_team_id=?, away_team_id=?, kickoff_utc=? WHERE id=?",
            [(h, a, k, fid) for fid, h, a, k in updates],
        )
        con.commit()
        print(f"  [APLICADO] {len(updates)} fixtures sincronizados.")
    elif updates:
        print("\n  [DRY-RUN] usa --apply para escribir.")
    con.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    run(ap.parse_args().apply)


if __name__ == "__main__":
    main()
