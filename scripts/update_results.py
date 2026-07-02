#!/usr/bin/env python
"""Marca como finished los partidos ya jugados, con marcador real de Polymarket.

Los resultados del Mundial 2026 no vienen de una API externa (datos simulados); la
fuente de verdad es la resolución de los mercados de Polymarket. Este script
reconstruye el marcador exacto de cada partido con kickoff pasado que sigue
'scheduled':
  - goles por equipo: ladder per-team "{H} vs. {A}: {Team} O/U N.5" resuelto.
  - si un equipo marcó 3+ (la ladder per-team llega a 2.5), se fija con el total
    del partido "{H} vs. {A}: O/U N.5" (llega a 8.5) menos los goles del rival.

Actualiza home_goals, away_goals, winner_team_id, status='finished'. Dry-run por
defecto; --apply para escribir.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8
from core.polymarket_client import build_public_client
from core.utils import utcnow
from venue.matching import canon as _canon

enable_utf8()

TAG = 102232
TID = "fifa_world_cup_2026"
REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / TID / f"{TID}.sqlite"
_MORE = re.compile(r"^(.+?)\s+vs\.?\s+(.+?)\s*-\s*More\s+Markets", re.I)


def _events(closed: bool) -> list:
    """Eventos WC vía el PublicClient del SDK (sin scraper Gamma)."""
    out: list = []
    for page in build_public_client().list_events(tag_ids=TAG, closed=closed, page_size=100):
        out.extend(page.items)
        if len(out) >= 1400:
            break
    return out


def _resolved(mk) -> str | None:
    """Label del outcome resuelto (precio ~1) de un Market del SDK, o None."""
    outs = getattr(mk, "outcomes", None)
    if outs is None:
        return None
    for oc in (getattr(outs, "yes", None), getattr(outs, "no", None)):
        if oc is not None and oc.price is not None and float(oc.price) > 0.98:
            return oc.label
    return None


def _bracket(over_lines: list[float], under_lines: list[float]) -> tuple[int, int]:
    lo = (max([int(x) + 1 for x in over_lines], default=0))
    hi = (min([int(x) for x in under_lines], default=99))
    return lo, hi


def _goals_from_event(ev: dict, home_disp: str, away_disp: str) -> tuple[int | None, int | None]:
    """Reconstruye (home_goals, away_goals) del More Markets resuelto."""
    team_over: dict[str, list[float]] = {}
    team_under: dict[str, list[float]] = {}
    tot_over: list[float] = []
    tot_under: list[float] = []
    for mk in (ev.markets or []):
        q = mk.question or ""
        if "Half" in q:
            continue
        lab = _resolved(mk)
        if lab is None:
            continue
        over = lab.lower() == "over"
        mteam = re.search(r":\s*(.+?)\s+O/U\s+(\d\.5)$", q)
        mtot = re.search(r":\s*O/U\s+(\d\.5)$", q)
        if mteam:
            team, line = mteam.group(1), float(mteam.group(2))
            target = team_over if over else team_under
            target.setdefault(team, []).append(line)
        elif mtot:
            line = float(mtot.group(1))
            (tot_over if over else tot_under).append(line)

    def team_goals(disp: str) -> int | None:
        # match el nombre del equipo dentro de las keys per-team
        key = next((t for t in set(team_over) | set(team_under) if _canon(t) == _canon(disp)), None)
        if key is None:
            return None
        lo, hi = _bracket(team_over.get(key, []), team_under.get(key, []))
        return lo if lo == hi else (lo, hi)  # type: ignore

    hg = team_goals(home_disp)
    ag = team_goals(away_disp)
    tlo, thi = _bracket(tot_over, tot_under)
    total = tlo if tlo == thi else None

    def pin(val, other):
        if isinstance(val, tuple):  # rango (ej. 3+): fijar con total - rival
            if total is not None and isinstance(other, int):
                return total - other
            return val[0]  # piso (3) como fallback
        return val
    hg2 = pin(hg, ag if isinstance(ag, int) else None)
    ag2 = pin(ag, hg if isinstance(hg, int) else None)
    return hg2, ag2


def run(apply: bool) -> None:
    events = {}
    for e in _events(True) + _events(False):
        m = _MORE.match(e.title or "")
        if m:
            events.setdefault(frozenset((_canon(m.group(1)), _canon(m.group(2)))), e)

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    now = utcnow().isoformat()
    past = con.execute(
        "SELECT id, home_team_id, away_team_id, kickoff_utc FROM fixture "
        "WHERE status='scheduled' AND kickoff_utc < ? ORDER BY kickoff_utc",
        (now,),
    ).fetchall()

    updates = []
    for f in past:
        ev = events.get(frozenset((_canon(f["home_team_id"].replace("_", " ")),
                                   _canon(f["away_team_id"].replace("_", " ")))))
        if not ev:
            continue
        hg, ag = _goals_from_event(ev, f["home_team_id"].replace("_", " "),
                                   f["away_team_id"].replace("_", " "))
        if not isinstance(hg, int) or not isinstance(ag, int):
            continue
        winner = f["home_team_id"] if hg > ag else (f["away_team_id"] if ag > hg else None)
        updates.append((f["id"], f["home_team_id"], f["away_team_id"], hg, ag, winner))

    print(f"Partidos a finalizar: {len(updates)}\n")
    for fid, h, a, hg, ag, w in updates:
        res = "empate" if w is None else f"gana {w}"
        print(f"  {fid:>6}  {h:>14} {hg}-{ag} {a:<14}  ({res})")

    if apply and updates:
        con.executemany(
            "UPDATE fixture SET home_goals=?, away_goals=?, winner_team_id=?, "
            "status='finished' WHERE id=?",
            [(hg, ag, w, fid) for fid, _, _, hg, ag, w in updates],
        )
        con.commit()
        print(f"\n[APLICADO] {len(updates)} partidos finalizados.")
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
