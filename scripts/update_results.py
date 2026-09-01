"""Marca como finished los partidos ya jugados, con marcador real de Polymarket.

Funciona para los torneos registrados con `polymarket_tag_id`. La fuente
de verdad del marcador es la resolución de los mercados de Polymarket:
  1. mercado "Exact Score" resuelto (Liga MX y ligas nuevas), o
  2. escalera O/U por equipo + total.
La lógica pura vive en `venue/results.py` (unit-testeable).

Actualiza home_goals, away_goals, winner_team_id, status='finished'.

    python scripts/update_results.py --tournament liga_mx_2026
    python scripts/update_results.py --tournament liga_mx_2026 --apply
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8
from core.utils import utcnow
from tournaments.registry import get_config
from venue.discovery import list_events
from venue.matching import canon as _canon
from venue.results import reconstruct_score

enable_utf8()

REPO = Path(__file__).resolve().parent.parent
_VS = re.compile(r"^(.+?)\s+vs\.?\s+(.+?)$", re.IGNORECASE)


def _pair_key(title: str) -> frozenset | None:
    """frozenset(canon(home), canon(away)) del título 'X vs. Y[ - Sufijo]'."""
    base = (title or "").split(" - ")[0]
    m = _VS.match(base.strip())
    if not m:
        return None
    return frozenset((_canon(m.group(1)), _canon(m.group(2))))


def collect_match_markets(tag_id: int) -> dict[frozenset, list]:
    """Todos los markets de PM agrupados por par de equipos (mezcla los eventos
    del partido: principal, Exact Score, More Markets, etc.)."""
    grouped: dict[frozenset, list] = {}
    for e in list_events(tag_id=tag_id, closed=True) + list_events(tag_id=tag_id, closed=False):
        key = _pair_key(e.title or "")
        if key is None or len(key) != 2:
            continue
        grouped.setdefault(key, []).extend(e.markets or [])
    return grouped


def run(tid: str, apply: bool) -> None:
    cfg = get_config(tid)
    if cfg.polymarket_tag_id is None:
        print(f"El torneo {tid} no tiene polymarket_tag_id en el registry.")
        return
    db = REPO / "data" / tid / f"{tid}.sqlite"
    markets_by_pair = collect_match_markets(cfg.polymarket_tag_id)

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    now = utcnow().isoformat()
    past = con.execute(
        "SELECT f.id, f.home_team_id, f.away_team_id, "
        "       h.name AS home_name, a.name AS away_name "
        "FROM fixture f JOIN team h ON h.id = f.home_team_id "
        "JOIN team a ON a.id = f.away_team_id "
        "WHERE f.status='scheduled' AND f.kickoff_utc < ? ORDER BY f.kickoff_utc",
        (now,),
    ).fetchall()

    updates = []
    for f in past:
        # display: nombre real de la tabla team (con aliases de venue/matching);
        # fallback al id sin guiones.
        home_disp = f["home_name"] or f["home_team_id"].replace("_", " ")
        away_disp = f["away_name"] or f["away_team_id"].replace("_", " ")
        mkts = (markets_by_pair.get(frozenset((_canon(home_disp), _canon(away_disp))))
                or markets_by_pair.get(frozenset((_canon(f["home_team_id"].replace("_", " ")),
                                                  _canon(f["away_team_id"].replace("_", " "))))))
        if not mkts:
            continue
        hg, ag = reconstruct_score(mkts, home_disp, away_disp)
        if not isinstance(hg, int) or not isinstance(ag, int):
            continue
        winner = f["home_team_id"] if hg > ag else (f["away_team_id"] if ag > hg else None)
        updates.append((f["id"], f["home_team_id"], f["away_team_id"], hg, ag, winner))

    print(f"[{cfg.display_name}] Partidos a finalizar: {len(updates)}\n")
    for fid, h, a, hg, ag, w in updates:
        res = "empate" if w is None else f"gana {w}"
        print(f"  {fid:>7}  {h:>18} {hg}-{ag} {a:<18}  ({res})")

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
    ap.add_argument("--tournament", default="liga_mx_2026")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    run(a.tournament, a.apply)


if __name__ == "__main__":
    main()
