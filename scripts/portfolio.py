#!/usr/bin/env python
"""Revisión del portafolio y los trades (abiertos, cerrados y pendientes) en consola.

Lee el estado local del agente (`data/agent_state.json`) y asienta el PnL de los
trades cerrados contra los resultados de los fixtures del SQLite del torneo.

    python scripts/portfolio.py                      # todo, bankroll por defecto
    python scripts/portfolio.py --bankroll 500
    python scripts/portfolio.py --tournament liga_mx_2026
    python scripts/portfolio.py --json               # salida JSON (para tooling)

Estados:
  ABIERTA   = ejecutada, el partido aún no termina (PnL no realizado, requiere live).
  CERRADA   = ejecutada, partido terminado → PnL asentado (WON/LOST).
  PENDIENTE = recomendada (REVIEW/approved), esperando aprobación humana. No apostada.
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from adapters.football.db_reader import FootballDBReader
from core.local_state import LocalStateClient
from portfolio.functions.trade_ledger import build_ledger

# Lector de resultados por deporte (sólo football por ahora; el resto queda sin asentar).
READERS = {"football": FootballDBReader}


def _load_results(decisions: list[dict]) -> dict[str, dict]:
    """Mapa event_id -> {status, home_team_id, away_team_id, winner_team_id}."""
    results: dict[str, dict] = {}
    readers: dict[str, object] = {}
    for dec in decisions:
        opp = dec.get("opportunity_json") or {}
        event_id = opp.get("event_id")
        tid, sport = dec.get("tournament_id"), dec.get("sport")
        if not event_id or event_id in results:
            continue
        reader_cls = READERS.get(sport)
        if reader_cls is None or not tid:
            continue
        reader = readers.get(tid)
        if reader is None:
            try:
                reader = reader_cls(tid)
            except Exception:
                continue
            readers[tid] = reader
        fx = reader.get_fixture(event_id)
        if fx is not None:
            results[event_id] = fx
    return results


def _money(x) -> str:
    return f"{Decimal(str(x)):+,.2f}"


def _price(x) -> str:
    return f"{Decimal(str(x)):.2f}" if x is not None else "  n/d"


def _kick(x) -> str:
    return str(x)[:16].replace("T", " ") if x else "?"


def _print_ledger(led: dict, tournament: str | None) -> None:
    s = led["summary"]
    scope = tournament or "todos los torneos"
    print(f"\n=== Portafolio — {scope} ===")
    print(f"    bankroll {Decimal(str(s['bankroll'])):,.2f}  ·  "
          f"equity {Decimal(str(s['equity'])):,.2f}  ·  "
          f"PnL realizado {_money(s['realized_pnl'])}  ·  ROI {s['roi'] * 100:+.1f}%")
    print(f"    abiertas {s['n_open']} (comprometido {Decimal(str(s['staked_open'])):,.2f})  ·  "
          f"cerradas {s['n_closed']} (W{s['wins']}-L{s['losses']}, "
          f"acierto {s['win_rate'] * 100:.0f}%)  ·  "
          f"pendientes {s['n_pending']} (reco {Decimal(str(s['pending_size'])):,.2f})")

    if led["open"]:
        print("\n  ── ABIERTAS ─────────────────────────────────────────────────────────")
        print(f"  {'PARTIDO':<32}{'PICK':<14}{'SIZE':>8}{'ENTRY':>7}{'EDGE':>8}  {'KICKOFF':<16}")
        for r in led["open"]:
            tag = "  (sin lado)" if r["outcome"] == "UNGRADED" else ""
            print(f"  {r['match'][:31]:<32}{str(r['pick'])[:13]:<14}"
                  f"{Decimal(str(r['size'])):>8,.2f}{_price(r['entry_price']):>7}"
                  f"{r['edge'] * 100:>+7.1f}%  {_kick(r['event_start']):<16}{tag}")

    if led["closed"]:
        print("\n  ── CERRADAS ─────────────────────────────────────────────────────────")
        print(f"  {'PARTIDO':<32}{'PICK':<14}{'RES':<5}{'ENTRY':>7}{'SIZE':>8}{'PnL':>10}")
        for r in led["closed"]:
            print(f"  {r['match'][:31]:<32}{str(r['pick'])[:13]:<14}{r['outcome']:<5}"
                  f"{_price(r['entry_price']):>7}{Decimal(str(r['size'])):>8,.2f}"
                  f"{_money(r['pnl']):>10}")

    if led["pending"]:
        print("\n  ── PENDIENTES (esperan aprobación del CIO) ──────────────────────────")
        print(f"  {'PARTIDO':<32}{'PICK':<14}{'VEREDICTO':<10}{'RECO':>8}{'EDGE':>8}  {'KICKOFF':<16}")
        for r in led["pending"]:
            print(f"  {r['match'][:31]:<32}{str(r['pick'])[:13]:<14}"
                  f"{str(r.get('verdict') or '?'):<10}{Decimal(str(r['size'])):>8,.2f}"
                  f"{r['edge'] * 100:>+7.1f}%  {_kick(r['event_start']):<16}")

    if not (led["open"] or led["closed"] or led["pending"]):
        print("\n    (sin decisiones registradas en el estado)")
    print()


def run(state_path: str, bankroll: float, tournament: str | None, as_json: bool) -> None:
    client = LocalStateClient(state_path, bankroll_usdc=bankroll)
    decisions = list(client._state.get("decisions", {}).values())
    if tournament:
        decisions = [d for d in decisions if d.get("tournament_id") == tournament]

    results = _load_results(decisions)
    led = build_ledger(decisions, results, bankroll=bankroll)

    if as_json:
        print(json.dumps(led, indent=2, default=str))
    else:
        _print_ledger(led, tournament)


def main() -> None:
    ap = argparse.ArgumentParser(description="Revisa el portafolio y los trades del agente.")
    ap.add_argument("--state", default="data/agent_state.json")
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--tournament", default=None, help="filtra por tournament_id")
    ap.add_argument("--json", action="store_true", help="salida JSON")
    a = ap.parse_args()
    run(a.state, a.bankroll, a.tournament, a.json)


if __name__ == "__main__":
    main()
