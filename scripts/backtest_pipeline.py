"""Ejecuta el backtest multitorneo del pipeline de decisión actual."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.workflows.pipeline_backtest import run
from core.console import enable_utf8
from core.exceptions import AgentError
from tournaments.registry import TOURNAMENTS

enable_utf8()


def _print(result: dict) -> None:
    perf = result["performance"]
    coverage = result["coverage"]
    decisions = result["decisions"]
    print(
        f"\n=== {result['tournament_id']} · {result['strategy']} "
        f"· season={result.get('season', 'n/d')} · as_of={str(result.get('as_of', ''))[:10]} ==="
    )
    print(
        f"  cobertura: {coverage['with_price']}/{coverage['games']} · "
        f"AUTO={decisions['AUTO']} REVIEW={decisions['REVIEW']} "
        f"DISCARD={decisions['DISCARD']} SKIP={decisions['SKIP']}"
    )
    print(
        f"  bets={perf['bets']} · {perf['wins']}W-{perf['losses']}L · "
        f"ROI={perf['roi']:+.1%} · yield={perf['yield_on_staked']:+.1%} · "
        f"maxDD={perf['max_drawdown']:.1%} · bankroll=${perf['bankroll_final']:,.2f}"
    )
    met = result["targets"]["met"]
    print(
        "  targets: "
        + ", ".join(f"{name}={'OK' if ok else 'FAIL'}" for name, ok in met.items())
    )
    print(f"  precios: {result['price_source']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tournament", default="all", choices=["all", *TOURNAMENTS])
    parser.add_argument("--season", default=None)
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--as-of", default=None, help="fecha de corte YYYY-MM-DD; default: hoy UTC")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    tournament_ids = list(TOURNAMENTS) if args.tournament == "all" else [args.tournament]
    results = []
    for tournament_id in tournament_ids:
        try:
            results.append(
                run(
                    tournament_id,
                    season=args.season,
                    bankroll=args.bankroll,
                    as_of=args.as_of,
                )
            )
        except (AgentError, FileNotFoundError, ValueError) as exc:
            results.append({"tournament_id": tournament_id, "available": False, "reason": str(exc)})

    if args.as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    for result in results:
        if result.get("available") is False:
            print(f"\n=== {result['tournament_id']} ===\n  no disponible: {result['reason']}")
        else:
            _print(result)


if __name__ == "__main__":
    main()
