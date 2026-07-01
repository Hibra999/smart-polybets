#!/usr/bin/env python
"""Corre el backtest NFL (TrueSkill + Kelly) y genera el reporte HTML con logos.

    python scripts/nfl_backtest_report.py --season 2025 --bankroll 1000
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.workflows import nfl_backtest
from editorial.functions.backtest_html import build_backtest_html
from editorial.functions.report_builder import save_report

# Logos del proyecto original (sports_bet/assets/logos/{apodo}.png).
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


def _load_logos() -> dict[str, str]:
    logos: dict[str, str] = {}
    for code, nick in CODE_NICK.items():
        p = LOGO_DIR / f"{nick}.png"
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            logos[code] = f"data:image/png;base64,{b64}"
    return logos


def run(season: int, bankroll: float) -> None:
    res = nfl_backtest.simulate(season=season, bankroll0=bankroll)
    print(f"Backtest {season}: {res['n_bets']} apuestas, ROI {res['roi'] * 100:+.1f}%, "
          f"bankroll {bankroll:.0f} -> {res['bankroll_final']:.2f}")
    logos = _load_logos()
    print(f"Logos cargados: {len(logos)}/32")
    html = build_backtest_html(res, logos)
    path = save_report("nfl_2026", html, suffix=f"backtest_{season}", ext="html")
    print(f"HTML: {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--bankroll", type=float, default=1000.0)
    a = ap.parse_args()
    run(a.season, a.bankroll)


if __name__ == "__main__":
    main()
