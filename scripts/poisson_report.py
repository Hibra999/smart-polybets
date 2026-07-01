#!/usr/bin/env python
"""Genera el reporte HTML combinado: backtest Qatar + recomendaciones + goles del día.

    POLYMARKET_PRIVATE_KEY=... python scripts/poisson_report.py --date 2026-06-23
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from adapters.football.db_reader import FootballDBReader
from adapters.football.wc_poisson_pipeline import WorldCupPoissonPipeline
from agent.workflows import daily_suggestions
from agent.workflows.wc_poisson_backtest import backtest
from editorial.functions.poisson_report import build_poisson_report
from editorial.functions.report_builder import save_report

TID = "fifa_world_cup_2026"
REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / TID / f"{TID}.sqlite"


def _qatar_matches() -> list[tuple[str, str, int, int]]:
    con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT home_team_id, away_team_id, home_goals, away_goals "
        "FROM historical_match ORDER BY match_date"
    ).fetchall()
    con.close()
    return [(r[0], r[1], r[2], r[3]) for r in rows]


def _goal_rows(date: str) -> list[dict]:
    reader = FootballDBReader(TID)
    fixtures = reader.query(
        "SELECT home_team_id, away_team_id FROM fixture "
        "WHERE status='scheduled' AND kickoff_utc LIKE ? ORDER BY kickoff_utc",
        (f"{date}%",),
    )
    pipe = WorldCupPoissonPipeline(TID).fit()
    rows = []
    for f in fixtures:
        h, a = f["home_team_id"], f["away_team_id"]
        fc = pipe.forecast(h, a)
        rows.append({
            "home": h, "away": a,
            "lambda_home": fc.lambda_home, "lambda_away": fc.lambda_away,
            "total": fc.expected_total, "over25": fc.prob_over(2.5),
            "btts": fc.prob_btts(), "result": fc.prob_result(),
            "confidence": fc.confidence(),
            "top_scores": fc.top_scores(3),
        })
    return rows


def run(date: str, bankroll: float, live: bool) -> None:
    bt = backtest(_qatar_matches(), min_team=2, warmup=16)

    market_source = None
    source = "polymarket"
    if live:
        from research.functions import PolymarketLiveSource
        market_source = PolymarketLiveSource()
        source = "polymarket-live"
    sugg = daily_suggestions.compute(date, TID, market_source=market_source,
                                     bankroll=bankroll, source_name=source)

    goals = _goal_rows(date)
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = build_poisson_report(
        backtest_res=bt, backtest_title="Qatar 2022 (48 partidos)",
        suggestions=sugg, goal_rows=goals, date=date, generated_at=gen,
    )
    path = save_report(TID, html, suffix="poisson_report", ext="html", date=date)
    print(f"Backtest Qatar: Over 2.5 BSS {bt['markets']['Over 2.5']['bss']:+.3f} "
          f"({bt['markets']['Over 2.5']['n']} part.)")
    print(f"Recomendaciones: {len(sugg['rows'])} partidos | Goles: {len(goals)} partidos")
    print(f"HTML: {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--bankroll", type=float, default=552.43)
    ap.add_argument("--no-live", action="store_true", help="usar cuotas snapshot en vez de live")
    a = ap.parse_args()
    run(a.date, a.bankroll, live=not a.no_live)


if __name__ == "__main__":
    main()
