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
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research.functions.polymarket_live import _canon

GAMMA = "https://gamma-api.polymarket.com"
TAG = 102232
UA = {"User-Agent": "Mozilla/5.0 (sports-quant-trading)"}
TID = "fifa_world_cup_2026"
REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / TID / f"{TID}.sqlite"
_TITLE = re.compile(r"^(.+?)\s+vs\.?\s+(.+?)\??$", re.I)


def _fetch(closed: str) -> list[dict]:
    out: list[dict] = []
    off = 0
    while len(out) < 1200:
        r = requests.get(f"{GAMMA}/events",
                         params={"tag_id": TAG, "limit": 100, "offset": off, "closed": closed},
                         headers=UA, timeout=20)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out += batch
        if len(batch) < 100:
            break
        off += 100
    return out


def _pm_times() -> dict[frozenset, str]:
    """frozenset(home_key, away_key) -> kickoff ISO (startTime real)."""
    index: dict[frozenset, str] = {}
    for e in _fetch("false") + _fetch("true"):
        title = (e.get("title") or "")
        if "More Markets" in title:
            continue
        m = _TITLE.match(title.split(" - ")[0].strip())
        if not m:
            continue
        st = e.get("startTime") or e.get("endDate")
        if not st:
            continue
        key = frozenset((_canon(m.group(1)), _canon(m.group(2))))
        # si hay duplicados, preferimos el primero (evento principal)
        index.setdefault(key, st)
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
