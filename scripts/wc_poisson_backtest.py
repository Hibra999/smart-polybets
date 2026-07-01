#!/usr/bin/env python
"""Corre el backtest de skill del modelo Poisson de goles e imprime las métricas.

    python scripts/wc_poisson_backtest.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.football.wc_poisson_pipeline import load_goal_matches
from agent.workflows.wc_poisson_backtest import backtest

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "fifa_world_cup_2026" / "fifa_world_cup_2026.sqlite"


def _hist_only() -> list[tuple[str, str, int, int]]:
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT home_team_id, away_team_id, home_goals, away_goals "
        "FROM historical_match ORDER BY match_date"
    ).fetchall()
    con.close()
    return [(r[0], r[1], r[2], r[3]) for r in rows]


def _print(title: str, res: dict) -> None:
    print(f"\n=== {title} ===  ({res['n_eval']} partidos evaluados)")
    print(f"{'MERCADO':10s}{'n':>4}{'base':>7}{'Brier_m':>9}{'Brier_base':>11}"
          f"{'BSS':>8}{'acc_m':>7}{'acc_base':>9}")
    for name, m in res["markets"].items():
        flag = "  <-- skill" if m["bss"] > 0 else ""
        print(f"{name:10s}{m['n']:>4}{m['base_rate']:>7.2f}{m['brier_model']:>9.3f}"
              f"{m['brier_base']:>11.3f}{m['bss']:>+8.3f}{m['acc_model']:>7.2f}"
              f"{m['acc_base']:>9.2f}{flag}")


def main() -> None:
    hist = _hist_only()
    allm = load_goal_matches()
    print(f"Datos: Qatar 2022 = {len(hist)} partidos | total (2022+2026) = {len(allm)}")
    _print("Qatar 2022 solo (predict-then-update, min_team=2, warmup=16)",
           backtest(hist, min_team=2, warmup=16))
    _print("Todo 2022+2026 con carryover (min_team=2, warmup=20)",
           backtest(allm, min_team=2, warmup=20))
    print("\nBSS (Brier Skill Score) > 0 = el modelo predice goles mejor que el "
          "promedio.\nBSS <= 0 = no aporta sobre la tasa base. No es consejo financiero.")


if __name__ == "__main__":
    main()
