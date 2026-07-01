#!/usr/bin/env python
"""Sugerencias de la estrategia activa para los partidos de una fecha (consola).

Imprime una tabla por partido (pick, modelo vs mercado, edge, veredicto, stake).
Reutiliza agent.workflows.daily_suggestions.compute (mismo cómputo que el HTML/tweet).

    python scripts/wc_suggestions.py --date 2026-06-20
    python scripts/wc_suggestions.py --date 2026-06-20 --live   # cuotas live de Polymarket
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from agent.workflows import daily_suggestions

TID = "fifa_world_cup_2026"


def _pct(x) -> str:
    return f"{x * 100:5.1f}%" if x is not None else "   n/d"


def run(date: str, bankroll: float, live: bool) -> None:
    market_source = None
    source_name = "polymarket"
    if live:
        from research.functions import PolymarketLiveSource
        market_source = PolymarketLiveSource()
        source_name = "polymarket-live"

    data = daily_suggestions.compute(
        date, TID, market_source=market_source, bankroll=bankroll, source_name=source_name,
    )
    print(f"\n=== Sugerencias WC {date} — estrategia '{data['strategy']}' "
          f"({data['side_criterion']}, kelly x{data['kelly_fraction']}) ===")
    print(f"    bankroll={bankroll:.0f} · cuotas={source_name} · {len(data['rows'])} partidos\n")
    if not data["rows"]:
        print("    (no hay partidos programados para esa fecha)")
        return

    print(f"{'PARTIDO':<34}{'PICK':<12}{'MODELO':>8}{'MERCADO':>9}{'EDGE':>8}  {'VEREDICTO':<10}{'STAKE':>8}")
    print("    " + "-" * 86)
    for r in data["rows"]:
        edge = f"{r['edge'] * 100:+6.1f}%" if r.get("edge") is not None else "   n/d"
        stake = f"{r['stake']:.2f}" if r.get("stake") else "0"
        print(f"{r['home']+' vs '+r['away']:<34}{str(r['pick_team'])[:11]:<12}"
              f"{_pct(r.get('model_prob')):>8}{_pct(r.get('market_prob')):>9}{edge:>8}  "
              f"{r['verdict']:<10}{stake:>8}")
        print(f"      └ elo {_pct(r.get('elo'))} · bayes {_pct(r.get('bayes'))} · "
              f"trueskill {_pct(r.get('trueskill'))} · conf {r.get('confidence')} · {r.get('reason','')}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    run(a.date, a.bankroll, a.live)


if __name__ == "__main__":
    main()
