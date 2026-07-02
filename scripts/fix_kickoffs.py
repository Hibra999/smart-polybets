#!/usr/bin/env python
"""Reemplaza los kickoff_utc sintéticos por los tiempos reales de Polymarket.

Los kickoff de la migración eran derivados del id (13:00, 13:30, ... por orden), no
los reales. Eso hacía fallar el gate de tiempo del riesgo (hours_to_event). Este
script trae el `startTime` real de cada evento de partido del Gamma API (abiertos y
cerrados), lo matchea a cada fixture por nombre canónico (la misma normalización
validada de polymarket_live, 135/135) y actualiza kickoff_utc.

Solo toca fixtures cuyo emparejamiento mapea a un evento de Polymarket; el resto
queda igual. Dry-run por defecto; --apply para escribir.

    python scripts/fix_kickoffs.py            # muestra el diff
    python scripts/fix_kickoffs.py --apply    # escribe
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8
from venue.discovery import match_events
from venue.matching import canon as _canon

enable_utf8()

TID = "fifa_world_cup_2026"
REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / TID / f"{TID}.sqlite"


def _pm_times() -> dict[frozenset, str]:
    """frozenset(home_canon, away_canon) -> kickoff ISO (schedule.start_time real).

    Vía el helper unificado `venue.discovery.match_events` (SDK, sin scraper Gamma).
    """
    index: dict[frozenset, str] = {}
    for me in match_events(closed=False) + match_events(closed=True):
        if me.kickoff is None:
            continue
        # si hay duplicados (ej. evento "More Markets"), preferimos el primero
        index.setdefault(frozenset((me.home_canon, me.away_canon)),
                         me.kickoff.astimezone(timezone.utc).isoformat())
    return index


def _norm_iso(st: str) -> str:
    """Normaliza '2026-06-23T17:00:00Z' / con micros -> 'YYYY-MM-DDTHH:MM:SS+00:00'."""
    st = st.replace("Z", "+00:00")
    st = re.sub(r"\.\d+", "", st)  # quita microsegundos
    if "+" not in st[10:] and "-" not in st[10:]:
        st += "+00:00"
    return st


def run(apply: bool) -> None:
    times = _pm_times()
    print(f"Eventos de Polymarket con tiempo: {len(times)}")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    fixtures = con.execute(
        "SELECT id, home_team_id, away_team_id, kickoff_utc FROM fixture ORDER BY kickoff_utc"
    ).fetchall()

    updates = []
    for f in fixtures:
        hk = _canon(f["home_team_id"].replace("_", " "))
        ak = _canon(f["away_team_id"].replace("_", " "))
        st = times.get(frozenset((hk, ak)))
        if not st:
            continue
        new = _norm_iso(st)
        if new[:16] != (f["kickoff_utc"] or "")[:16]:
            updates.append((f["id"], f["home_team_id"], f["away_team_id"],
                            f["kickoff_utc"], new))

    print(f"Fixtures que cambian: {len(updates)} / {len(fixtures)}\n")
    for fid, h, a, old, new in updates[:30]:
        print(f"  {fid:>6} {h:>14} vs {a:<14} {(old or '')[:16]} -> {new[:16]}")
    if len(updates) > 30:
        print(f"  ... y {len(updates) - 30} mas")

    if apply and updates:
        con.executemany("UPDATE fixture SET kickoff_utc=? WHERE id=?",
                        [(new, fid) for fid, _, _, _, new in updates])
        con.commit()
        print(f"\n[APLICADO] {len(updates)} kickoffs actualizados en {DB.name}")
    elif updates:
        print("\n[DRY-RUN] usa --apply para escribir.")
    con.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    run(a.apply)


if __name__ == "__main__":
    main()
