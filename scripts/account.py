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
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.timez import fmt_local_et, to_local

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8
from core.env import load_env

enable_utf8()  # consola Windows: stdout/stderr en UTF-8
load_env(Path(__file__).resolve().parent.parent / ".env")  # POLYMARKET_PRIVATE_KEY, etc.

from agent.tools import account_tools
from core.exceptions import AccountUnavailableError
from core.local_state import LocalStateClient
from portfolio.functions.account_reconcile import reconcile
from portfolio.functions.account_source import PolymarketAccountSource
from core.preconditions import enforce as enforce_freshness


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
        tournament: str | None, do_reconcile: bool, as_json: bool, closed_n: int) -> None:
    # PnL/cuenta transversal → evalúa TODOS los torneos activos (aviso, no bloquea).
    enforce_freshness("READ")
    client = LocalStateClient(state_path, bankroll_usdc=bankroll)
    decisions = list(client._state.get("decisions", {}).values())
    source = PolymarketAccountSource()

    try:
        # Trae TODAS las cerradas (ganadas) para que el PnL neto de RESUELTAS sea real,
        # no solo las últimas N (las perdidas -cur=0- ya vienen completas en positions).
        snap = account_tools.account_snapshot(
            source, price_of=None, decisions=decisions, closed_limit=max(closed_n, 100))
    except AccountUnavailableError as exc:
        print(f"\n  Cuenta live no disponible: {exc}")
        print('  (instala el extra live: pip install --pre -e ".[live]" y define POLYMARKET_PRIVATE_KEY)\n')
        return

    positions = [p for p in snap["positions"]
                 if _match_filter(p.event_id, p.tournament_id, event, tournament)]
    orders = [o for o in snap["open_orders"]
              if _match_filter(o.event_id, o.tournament_id, event, tournament)]
    closed = snap["closed"]
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
            "closed": [c.model_dump(mode="json") for c in closed],
            # PnL neto autoritativo (cuadra con la UI); None si la fuente no expone trades.
            "realized_pnl": (str(snap["realized_pnl"]) if snap.get("realized_pnl") is not None else None),
            "trades": [t.model_dump(mode="json") for t in snap.get("trades", [])],
            "redemptions": [r.model_dump(mode="json") for r in snap.get("redemptions", [])],
        }, indent=2, default=str))
        return

    def _tag(obj) -> str:
        return obj.title or obj.event_id or (obj.condition_id[:12] + "…")

    print(f"\n=== Cuenta Polymarket (as_of {fmt_local_et(balance.as_of)}) ===")
    print("    (horas en PDC/UTC-5; Polymarket etiqueta sus mercados en ET = PDC+1h en verano)")
    print(f"    saldo pUSD: {_dec(balance.usdc_balance)}"
          + (f"  ·  wallet {balance.address}" if balance.address else ""))

    # Posiciones VIVAS (precio > 0) vs RESUELTAS-PERDIDAS (precio 0, sin redimir).
    live = [p for p in positions if p.current_price is None or p.current_price > 0]
    lost = [p for p in positions if p.current_price is not None and p.current_price == 0]

    upnl = sum((p.unrealized_pnl for p in live if p.unrealized_pnl is not None), Decimal("0"))
    print(f"\n  ── POSICIONES ABIERTAS ({len(live)}) · uPnL {_pnl(upnl)} ──────────────")
    print(f"  {'MERCADO':<34}{'OUT':<5}{'SHARES':>10}{'ENTRY':>7}{'PRICE':>7}{'uPnL':>10}")
    for p in live:
        price = "  n/d" if p.current_price is None else f"{p.current_price:.2f}"
        print(f"  {_tag(p)[:33]:<34}{p.outcome[:4]:<5}{p.size_shares:>10,.2f}"
              f"{p.avg_entry_price:>7.2f}{price:>7}{_pnl(p.unrealized_pnl):>10}")

    if orders:
        print(f"\n  ── ÓRDENES ABIERTAS ({len(orders)}) ──────────────────────────────────")
        print(f"  {'MERCADO':<34}{'SIDE':<5}{'PRICE':>7}{'SIZE':>10}{'MATCHED':>10}")
        for o in orders:
            print(f"  {_tag(o)[:33]:<34}{o.side[:4]:<5}{o.price:>7.2f}"
                  f"{o.size_shares:>10,.2f}{o.size_matched:>10,.2f}")

    # RESUELTAS: fusiona ganadas (cerradas, redimidas) + PERDIDAS (posiciones a 0).
    def _date(obj, attr):
        d = getattr(obj, attr, None)
        if d is not None:
            return to_local(d).strftime("%Y-%m-%d")  # fecha local (PDC)
        m = re.search(r"\d{4}-\d{2}-\d{2}", getattr(obj, "title", "") or "")
        return m.group(0) if m else "?"  # fallback: fecha del título (ET de Poly)
    resolved = [(_date(c, "closed_at"), _tag(c), c.outcome, c.avg_price, c.realized_pnl, True)
                for c in closed]
    resolved += [(_date(p, "closed_at"), _tag(p), p.outcome, p.avg_entry_price,
                  -(p.size_shares * p.avg_entry_price), False) for p in lost]
    resolved.sort(key=lambda x: x[0], reverse=True)
    net_snapshot = sum((r[4] for r in resolved), Decimal("0"))
    # PnL neto AUTORITATIVO = flujo de caja (Σ ventas + Σ redenciones − Σ compras);
    # cuadra con la UI de Polymarket. El snapshot sobreestima pérdidas cuando hubo
    # cierres anticipados (salvamento). Ver docs/findings/2026-07-17-pnl-cashflow-vs-snapshot.md.
    net_cf = snap.get("realized_pnl")
    net = net_cf if net_cf is not None else net_snapshot
    wins = sum(1 for r in resolved if r[5])
    losses = sum(1 for r in resolved if not r[5])
    print(f"\n  ── RESUELTAS ({len(resolved)}: {wins}W-{losses}L) · PnL neto {_pnl(net)} ──────────────")
    print(f"  {'FECHA':<12}{'MERCADO':<34}{'RES':<8}{'ENTRY':>7}{'PnL':>10}")
    for d, tag, outc, entry, pnl, won in resolved:
        print(f"  {d:<12}{str(tag)[:33]:<34}{'GANÓ' if won else 'PERDIÓ':<8}"
              f"{Decimal(str(entry)):>7.2f}{_pnl(pnl):>10}")
    if net_cf is not None and abs(net_cf - net_snapshot) >= Decimal("0.01"):
        salv = net_cf - net_snapshot
        print(f"\n  reconciliación: Σ filas (snapshot) {_pnl(net_snapshot)} · "
              f"salvamento de cierres anticipados {_pnl(salv)} · "
              f"PnL neto real (flujo de caja) {_pnl(net_cf)}")
        print("  (las filas 'PERDIÓ' asumen pérdida total; vender antes de la resolución recupera parte)")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="Cuenta live de Polymarket (saldo/posiciones/órdenes).")
    ap.add_argument("--state", default="data/agent_state.json")
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--event", default=None, help="filtra por event_id")
    ap.add_argument("--tournament", default=None, help="filtra por tournament_id")
    ap.add_argument("--reconcile", action="store_true", help="drift vs estado local + ajusta bankroll")
    ap.add_argument("--closed", type=int, default=6, help="cuántas posiciones cerradas mostrar")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    run(a.state, a.bankroll, a.event, a.tournament, a.reconcile, a.json, a.closed)


if __name__ == "__main__":
    main()
