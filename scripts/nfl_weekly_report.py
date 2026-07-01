#!/usr/bin/env python
"""Backtest NFL semana a semana → HTML con logos y comentarios.

    python scripts/nfl_weekly_report.py --model trueskill --side dog --season 2025
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.workflows import nfl_ensemble_backtest as eb
from editorial.functions.report_builder import save_report
from editorial.functions.weekly_backtest_html import build_weekly_html

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
WEIGHTS = {"elo": {"elo": 1}, "bayes": {"bayes": 1}, "trueskill": {"trueskill": 1},
           "blend": {"elo": 1, "trueskill": 1, "bayes": 1}}


def _load_logos() -> dict[str, str]:
    out: dict[str, str] = {}
    for code, nick in CODE_NICK.items():
        p = LOGO_DIR / f"{nick}.png"
        if p.exists():
            out[code] = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    return out


def run(model: str, side: str, season: int, devig: bool, kelly: float) -> None:
    dogs = side == "dog"
    res = eb.simulate_combo(eb.load_games(), WEIGHTS[model], season=season, devig=devig,
                            edge_threshold=0.0, kelly_fraction=kelly, underdogs_only=dogs,
                            per_season_reset=True, collect_bets=True)
    cfg = {"Modelo": model, "Lado": "underdogs" if dogs else "favorito",
           "Linea": "sin vig" if devig else "real", "Kelly": kelly, "Reset": "por temporada"}
    html = build_weekly_html(res, _load_logos(), cfg)
    path = save_report("nfl_2026", html, suffix=f"weekly_{model}_{side}_{season}", ext="html")
    print(f"{model}/{side} {season}: {res['n_bets']} apuestas, ROI {res['roi']*100:+.1f}% -> {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="trueskill", choices=list(WEIGHTS))
    ap.add_argument("--side", default="dog", choices=["dog", "fav"])
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--devig", action="store_true")
    ap.add_argument("--kelly", type=float, default=0.4)
    a = ap.parse_args()
    run(a.model, a.side, a.season, a.devig, a.kelly)


if __name__ == "__main__":
    main()
