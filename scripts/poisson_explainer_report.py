#!/usr/bin/env python
"""Genera el explainer HTML de cómo funciona el modelo de goles.

    python scripts/poisson_explainer_report.py
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.football.wc_poisson_pipeline import WorldCupPoissonPipeline
from agent.workflows.wc_poisson_backtest import backtest
from editorial.functions.poisson_explainer import build_poisson_explainer
from editorial.functions.report_builder import save_report

TID = "fifa_world_cup_2026"
REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / TID / f"{TID}.sqlite"


def _qatar() -> list[tuple[str, str, int, int]]:
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    rows = con.execute("SELECT home_team_id, away_team_id, home_goals, away_goals "
                       "FROM historical_match ORDER BY match_date").fetchall()
    con.close()
    return [(r[0], r[1], r[2], r[3]) for r in rows]


def _example(home: str, away: str) -> dict:
    p = WorldCupPoissonPipeline(TID).fit()
    m, fc = p.model, p.forecast(home, away)
    rh, ra = m.team(home), m.team(away)
    return {
        "base": round(m.base, 3), "home_factor": round(m.home_factor, 3),
        "neutral": m.neutral, "n_teams": len(m.rates), "home": home, "away": away,
        "atk_h": round(rh.attack, 3), "def_h": round(rh.defense, 3), "mh": rh.matches,
        "atk_a": round(ra.attack, 3), "def_a": round(ra.defense, 3), "ma": ra.matches,
        "lh": round(fc.lambda_home, 3), "la": round(fc.lambda_away, 3),
        "tot": round(fc.expected_total, 3),
        "over25": fc.prob_over(2.5), "btts": fc.prob_btts(),
        "res": fc.prob_result(), "tops": fc.top_scores(4), "conf": fc.confidence(),
    }


def run(home: str, away: str) -> None:
    ex = _example(home, away)
    bt = backtest(_qatar(), min_team=2, warmup=16)
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = build_poisson_explainer(example=ex, backtest=bt, generated_at=gen)
    path = save_report("_system", html, suffix="poisson_explainer", ext="html")
    print(f"Ejemplo: {home} {ex['lh']} - {ex['la']} {away} | Over2.5 {ex['over25']:.1%}")
    print(f"Explainer: {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", default="england")
    ap.add_argument("--away", default="ghana")
    a = ap.parse_args()
    run(a.home, a.away)


if __name__ == "__main__":
    main()
