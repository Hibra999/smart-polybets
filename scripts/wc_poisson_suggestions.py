#!/usr/bin/env python
"""Pronóstico de GOLES (modelo Poisson) para los partidos de una fecha.

Modelo complementario: predice goles, no ganador. Imprime, por partido, los goles
esperados de cada lado y las probabilidades de los mercados Over/Under 2.5, BTTS,
1X2-por-goles y los marcadores más probables.

    python scripts/wc_poisson_suggestions.py --date 2026-06-23

Requiere la tabla historical_match (corré antes scripts/migrate_poisson_history.py).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from adapters.football.db_reader import FootballDBReader
from adapters.football.wc_poisson_pipeline import WorldCupPoissonPipeline
from tournaments.registry import get_config

TID = "fifa_world_cup_2026"


def _pct(x: float) -> str:
    return f"{x * 100:4.1f}%"


def run(date: str, line: float, tid: str = TID) -> None:
    cfg = get_config(tid)
    reader = FootballDBReader(tid)
    fixtures = reader.query(
        "SELECT id, home_team_id, away_team_id FROM fixture "
        "WHERE status='scheduled' AND kickoff_utc LIKE ? ORDER BY kickoff_utc",
        (f"{date}%",),
    )
    # neutral según el torneo: el Mundial no tiene localía; una liga sí.
    pipe = WorldCupPoissonPipeline(tid, neutral=cfg.neutral_venue).fit()
    n_fit = len(pipe.model.rates)
    print(f"\n=== Poisson de goles, {cfg.display_name} {date} "
          f"({'sede neutral' if cfg.neutral_venue else 'con localía'}) ===")
    print(f"    base={pipe.model.base:.2f} goles/equipo  home_factor={pipe.model.home_factor:.2f}  "
          f"{n_fit} equipos ajustados\n")
    if not fixtures:
        print("    (sin partidos programados esa fecha)")
        return

    for f in fixtures:
        h, a = f["home_team_id"], f["away_team_id"]
        fc = pipe.forecast(h, a)
        res = fc.prob_result()
        over = fc.prob_over(line)
        tops = fc.top_scores(3)
        scores = ", ".join(f"{i}-{j} ({_pct(p)})" for i, j, p in tops)
        print(f"{h} vs {a}   [conf {fc.confidence()}]")
        print(f"    Goles esperados : {h} {fc.lambda_home:.2f} - {fc.lambda_away:.2f} {a}  "
              f"(total {fc.expected_total:.2f})")
        print(f"    Over {line:g} {_pct(over)}   Under {line:g} {_pct(1 - over)}   "
              f"BTTS {_pct(fc.prob_btts())}")
        print(f"    1X2 por goles   : {h} {_pct(res['home'])}  empate {_pct(res['draw'])}  "
              f"{a} {_pct(res['away'])}")
        print(f"    Marcadores      : {scores}\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--line", type=float, default=2.5, help="línea Over/Under")
    ap.add_argument("--tournament", default=TID)
    a = ap.parse_args()
    run(a.date, a.line, a.tournament)


if __name__ == "__main__":
    main()
