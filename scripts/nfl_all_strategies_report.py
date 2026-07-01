#!/usr/bin/env python
"""Backtest combinado de TODAS las estrategias (modelo x lado) en un solo HTML.

    python scripts/nfl_all_strategies_report.py --season 2025
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from agent.workflows import nfl_ensemble_backtest as eb
from editorial.functions.report_builder import save_report
from editorial.functions.weekly_backtest_html import build_multi_weekly_html

LOGO_DIR = Path(r"C:\0_documentos\educacion\pypro\sports_bet\assets\logos")
CODE_NICK = {
    "ARI": "cardinals", "ATL": "falcons", "BAL": "ravens", "BUF": "bills",
    "CAR": "panthers", "CHI": "bears", "CIN": "bengals", "CLE": "browns",
    "DAL": "cowboys", "DEN": "broncos", "DET": "lions", "GB": "packers",
    "HOU": "texans", "IND": "colts", "JAX": "jaguars", "KC": "chiefs",
    "LV": "raiders", "LAC": "chargers", "LAR": "rams", "LA": "rams",
    "MIA": "dolphins", "MIN": "vikings", "NE": "patriots", "NO": "saints",
    "NYG": "giants", "NYJ": "jets", "PHI": "eagles", "PIT": "steelers",
    "SF": "49ers", "SEA": "seahawks", "TB": "buccaneers", "TEN": "titans",
    "WAS": "commanders",
}
WEIGHTS = {"Elo": {"elo": 1}, "Bayes": {"bayes": 1}, "TrueSkill": {"trueskill": 1},
           "Blend": {"elo": 1, "trueskill": 1, "bayes": 1}}


def _load_logos() -> dict[str, str]:
    out: dict[str, str] = {}
    for code, nick in CODE_NICK.items():
        p = LOGO_DIR / f"{nick}.png"
        if p.exists():
            out[code] = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    return out


def run(season: int, kelly: float) -> None:
    games = eb.load_games()
    strategies = []
    for model, w in WEIGHTS.items():
        for side, dogs in [("favorito", False), ("underdog", True)]:
            res = eb.simulate_combo(games, w, season=season, devig=False, edge_threshold=0.0,
                                    kelly_fraction=kelly, underdogs_only=dogs,
                                    per_season_reset=True, collect_bets=True)
            strategies.append({"label": f"{model} · {side}", "res": res})
            print(f"  {model:>10} {side:>9}: {res['n_bets']:>3} apuestas  ROI {res['roi']*100:>+6.1f}%")
    html = build_multi_weekly_html(strategies, _load_logos(), season)
    path = save_report("nfl_2026", html, suffix=f"all_strategies_{season}", ext="html")
    print(f"HTML combinado: {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--kelly", type=float, default=0.4)
    a = ap.parse_args()
    run(a.season, a.kelly)


if __name__ == "__main__":
    main()
