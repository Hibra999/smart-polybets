#!/usr/bin/env python
"""Cuenta live de Polymarket en consola: saldo, posiciones y órdenes abiertas.

    python scripts/account.py                       # snapshot (todas las posiciones)
    python scripts/account.py --event wc_49         # filtra por evento
    python scripts/account.py --tournament fifa_world_cup_2026
    python scripts/account.py --reconcile           # drift vs estado local + ajusta bankroll
    python scripts/account.py --json

Requiere el SDK live (`pip install --pre -e ".[live]"`) + `POLYMARKET_PRIVATE_KEY`.
Sin ellos, informa que la cuenta live no está disponible (no rompe).
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

from agent.tools import account_tools
from core.exceptions import AccountUnavailableError
from core.local_state import LocalStateClient
from portfolio.functions.account_reconcile import reconcile
from portfolio.functions.account_source import PolymarketAccountSource


def _dec(x) -> str:
    return f"{Decimal(str(x)):,.2f}"


def _pnl(x) -> str:
    return "   n/d" if x is None else f"{Decimal(str(x)):+,.2f}"


def _match_filter(tag_event, tag_tournament, event, tournament) -> bool:
    if event and tag_event != event:
        return False
    if tournament and tag_tournament != tournament:
        return False
    return True


def run(state_path: str, bankroll: float, event: str | None,
        tournament: str | None, do_reconcile: bool, as_json: bool) -> None:
    client = LocalStateClient(state_path, bankroll_usdc=bankroll)
    decisions = list(client._state.get("decisions", {}).values())
    source = PolymarketAccountSource()

    try:
        snap = account_tools.account_snapshot(source, price_of=None, decisions=decisions)
    except AccountUnavailableError as exc:
        print(f"\n  Cuenta live no disponible: {exc}")
        print('  (instala el extra live: pip install --pre -e ".[live]" y define POLYMARKET_PRIVATE_KEY)\n')
        return

    positions = [p for p in snap["positions"]
                 if _match_filter(p.event_id, p.tournament_id, event, tournament)]
    orders = [o for o in snap["open_orders"]
              if _match_filter(o.event_id, o.tournament_id, event, tournament)]
    balance = snap["balance"]

    if do_reconcile:
        rep = reconcile(decisions, balance, snap["positions"],
                        bankroll_param=client.initial_bankroll)
        if as_json:
            print(json.dumps(rep, indent=2, default=str))
        else:
            print(f"\n=== Reconciliación (as_of {rep['as_of']}) ===")
            print(f"    bankroll_param {_dec(rep['bankroll_param'])}  ·  "
                  f"balance real {_dec(rep['balance_real'])}  ·  "
                  f"delta {_pnl(rep['bankroll_delta'])}")
            print(f"    posiciones live {rep['n_live_positions']}  ·  "
                  f"ejecutadas local {rep['n_executed_local']}")
            if rep["missing_fills"]:
                print(f"    sin fill on-chain: {', '.join(rep['missing_fills'])}")
            if rep["external_positions"]:
                print(f"    externas (no en ledger): {', '.join(rep['external_positions'])}")
            print(f"    bankroll local ajustado a {_dec(balance.usdc_balance)}\n")
        # Única escritura: ajustar el bankroll local al balance real (ambos modos).
        client.set_bankroll(balance.usdc_balance)
        return

    if as_json:
        print(json.dumps({
            "balance": balance.model_dump(mode="json"),
            "positions": [p.model_dump(mode="json") for p in positions],
            "open_orders": [o.model_dump(mode="json") for o in orders],
        }, indent=2, default=str))
        return

    print(f"\n=== Cuenta Polymarket (as_of {balance.as_of.isoformat(timespec='minutes')}) ===")
    print(f"    saldo pUSD: {_dec(balance.usdc_balance)}")

    print(f"\n  ── POSICIONES ({len(positions)}) ─────────────────────────────────────")
    print(f"  {'EVENTO/COND':<20}{'OUT':<5}{'SHARES':>10}{'ENTRY':>7}{'PRICE':>7}{'uPnL':>10}")
    for p in positions:
        tag = p.event_id or (p.condition_id[:10] + "…")
        price = "  n/d" if p.current_price is None else f"{p.current_price:.2f}"
        print(f"  {str(tag)[:19]:<20}{p.outcome[:4]:<5}{p.size_shares:>10,.2f}"
              f"{p.avg_entry_price:>7.2f}{price:>7}{_pnl(p.unrealized_pnl):>10}")

    print(f"\n  ── ÓRDENES ABIERTAS ({len(orders)}) ──────────────────────────────────")
    print(f"  {'EVENTO/COND':<20}{'SIDE':<5}{'PRICE':>7}{'SIZE':>10}{'MATCHED':>10}")
    for o in orders:
        tag = o.event_id or (o.condition_id[:10] + "…")
        print(f"  {str(tag)[:19]:<20}{o.side[:4]:<5}{o.price:>7.2f}"
              f"{o.size_shares:>10,.2f}{o.size_matched:>10,.2f}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="Cuenta live de Polymarket (saldo/posiciones/órdenes).")
    ap.add_argument("--state", default="data/agent_state.json")
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--event", default=None, help="filtra por event_id")
    ap.add_argument("--tournament", default=None, help="filtra por tournament_id")
    ap.add_argument("--reconcile", action="store_true", help="drift vs estado local + ajusta bankroll")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    run(a.state, a.bankroll, a.event, a.tournament, a.reconcile, a.json)


if __name__ == "__main__":
    main()
