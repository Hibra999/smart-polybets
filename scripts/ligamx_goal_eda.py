#!/usr/bin/env python
"""EDA de minutos de gol de Liga MX — insumo para modelar las reglas del theta trade.

Preguntas que responde (con la 2025/26 de ESPN + favoritos del cierre de football-data):
  1. ¿Cuándo se anota en Liga MX? (hazard por bin de 15', 1T vs 2T, descuentos)
  2. ¿Cuánto vive el 0-0? (supervivencia: P(sin gol) al min 15/30/45/60/75/90)
  3. ¿Cuándo anota EL FAVORITO? — el riesgo de gap del theta lay:
     P(favorito ya anotó antes del min m) y su hazard por bin.
  4. Rojas: frecuencia y timing (mueven el precio como un gol).
  5. Implicaciones directas para from_min / hard_exit_min del STRATEGY.md.

    python scripts/ligamx_goal_eda.py

Requiere: fetch_goal_minutes_espn.py --apply (timeline) + MEX.csv (favoritos).
"""
from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()

from scripts.ligamx_backtest import load_matches

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "liga_mx_2026" / "liga_mx_2026.sqlite"
CHECKPOINTS = (15, 30, 45, 60, 75, 90)


def load_timeline():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM match_timeline_event WHERE home_team_id IS NOT NULL "
        "AND away_team_id IS NOT NULL")]
    con.close()
    return rows


def favorites_by_match() -> dict[frozenset, tuple[str, str, float]]:
    """{(date, {home,away})-ish: (fav_slug, dog_slug, fav_odds)} desde el cierre."""
    out = {}
    for m in load_matches({"2025/2026"}):
        if not (m["oh"] and m["oa"]):
            continue
        fav = m["home"] if m["oh"] < m["oa"] else m["away"]
        dog = m["away"] if fav == m["home"] else m["home"]
        for delta in (-1, 0, 1):
            key = (m["date"].date() + timedelta(days=delta), frozenset((m["home"], m["away"])))
            out.setdefault(key, (fav, dog, min(m["oh"], m["oa"])))
    return out


def main() -> None:
    events = load_timeline()
    favs = favorites_by_match()

    # agrupar por partido
    matches: dict[str, dict] = {}
    for e in events:
        mkey = e["espn_event_id"]
        m = matches.setdefault(mkey, {
            "date": date.fromisoformat(e["match_date"]),
            "home": e["home_team_id"], "away": e["away_team_id"],
            "goals": [], "reds": []})
        if e["event_type"] == "red_card":
            m["reds"].append(e)
        else:
            m["goals"].append(e)

    # anotar favorito
    n_fav = 0
    for m in matches.values():
        fk = (m["date"], frozenset((m["home"], m["away"])))
        info = favs.get(fk)
        m["fav"] = info[0] if info else None
        n_fav += bool(info)

    all_goals = [g for m in matches.values() for g in m["goals"]]
    n = len(matches)
    print(f"=== EDA goles Liga MX 2025/26 (ESPN) ===")
    print(f"partidos: {n} · goles: {len(all_goals)} ({len(all_goals)/n:.2f}/partido) · "
          f"con favorito identificado: {n_fav}")

    # 1. hazard por bin de 15'
    bins = defaultdict(int)
    for g in all_goals:
        b = min(int((g["minute_base"] - 1) // 15) * 15, 75) if g["minute_base"] <= 90 else 75
        label = f"{b+1:02d}-{b+15}" if g["minute_extra"] == 0 or g["minute_base"] not in (45, 90) \
            else f"{b+1:02d}-{b+15}"
        bins[f"{b+1:02d}-{b+15}"] += 1
    stoppage_1t = sum(1 for g in all_goals if g["minute_base"] == 45 and g["minute_extra"] > 0)
    stoppage_2t = sum(1 for g in all_goals if g["minute_base"] >= 90)
    print("\n-- goles por bin de 15 min --")
    for k in sorted(bins):
        pct = bins[k] / len(all_goals)
        print(f"  {k}': {bins[k]:4d}  ({pct:5.1%})  {'█' * int(pct * 120)}")
    t1 = sum(1 for g in all_goals if g["minute_base"] <= 45)
    print(f"  1T: {t1/len(all_goals):.1%} (desc. 45+: {stoppage_1t}) · "
          f"2T: {1 - t1/len(all_goals):.1%} (desc. 90+: {stoppage_2t})")

    # 2. supervivencia del 0-0 y del "favorito sin anotar"
    print("\n-- supervivencia (P de llegar al minuto m) --")
    print(f"  {'m':>4} {'sin goles (0-0)':>16} {'favorito sin anotar':>21}")
    for cp in CHECKPOINTS:
        alive00 = sum(1 for m in matches.values()
                      if not any(g["minute"] <= cp for g in m["goals"]))
        fav_ok = fav_tot = 0
        for m in matches.values():
            if m["fav"] is None:
                continue
            fav_tot += 1
            fav_side = "home" if m["fav"] == m["home"] else "away"
            if not any(g["side"] == fav_side and g["minute"] <= cp for g in m["goals"]):
                fav_ok += 1
        print(f"  {cp:>4} {alive00/n:>15.1%} {fav_ok/fav_tot if fav_tot else 0:>20.1%}")

    # 3. primer gol
    firsts = [min(g["minute"] for g in m["goals"]) for m in matches.values() if m["goals"]]
    firsts.sort()
    med = firsts[len(firsts)//2] if firsts else None
    p_no_goal = sum(1 for m in matches.values() if not m["goals"]) / n
    print(f"\n-- primer gol --  mediana min {med:.0f} · partidos sin goles: {p_no_goal:.1%}")

    # 4. rojas
    reds = [r for m in matches.values() for r in m["reds"]]
    red_matches = sum(1 for m in matches.values() if m["reds"])
    if reds:
        med_red = sorted(r["minute"] for r in reds)[len(reds)//2]
        print(f"-- rojas --  {len(reds)} en {red_matches} partidos ({red_matches/n:.0%} de partidos) · "
              f"mediana min {med_red:.0f}")

    # 5. implicaciones para el theta
    print("\n-- implicaciones para theta_lay_v1 --")
    for cp in (30, 45, 60, 75):
        fav_scored = fav_tot = 0
        for m in matches.values():
            if m["fav"] is None:
                continue
            fav_tot += 1
            fav_side = "home" if m["fav"] == m["home"] else "away"
            fav_scored += any(g["side"] == fav_side and g["minute"] <= cp for g in m["goals"])
        print(f"  P(favorito YA anotó antes del min {cp}): {fav_scored/fav_tot:.1%}"
              f"   (riesgo de gap acumulado si seguimos adentro)")


if __name__ == "__main__":
    main()
