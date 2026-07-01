#!/usr/bin/env python
"""Aprobar decisiones REVIEW → colocar la orden real, y cancelar órdenes abiertas.

    python scripts/orders.py --list                       # REVIEWs pendientes + órdenes abiertas
    python scripts/orders.py --approve <key> [--live]      # coloca la orden de esa decisión
    python scripts/orders.py --cancel <order_id> [--live]  # cancela una orden abierta

DINERO REAL: sin --live (+ POLYMARKET_LIVE=1 + key + kill-switch off) todo es dry-run.
Además, cada colocación/cancelación pide CONFIRMACIÓN TIPEADA (o --confirm <valor>).
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8
from core.env import load_env

enable_utf8()
load_env(Path(__file__).resolve().parent.parent / ".env")

from agent.tools import account_tools
from core.exceptions import AccountUnavailableError
from core.local_state import LocalStateClient
from core.utils import to_decimal, utcnow
from execution.functions.broker import PolymarketBroker
from execution.functions.review_order import (
    build_trade_order_from_decision,
    validate_placeable,
)
from portfolio.functions.account_source import PolymarketAccountSource


def _pending_reviews(decisions: dict) -> list[tuple[str, dict]]:
    out = []
    for key, d in decisions.items():
        if d.get("status") == "pending_approval" or d.get("verdict") == "REVIEW":
            out.append((key, d))
    return out


def _confirm(expected: str, provided: str | None) -> bool:
    if provided is not None:
        return provided.strip() == expected
    try:
        typed = input(f"    Para confirmar, escribí exactamente '{expected}': ")
    except EOFError:
        return False
    return typed.strip() == expected


def cmd_list(decisions: dict) -> None:
    reviews = _pending_reviews(decisions)
    print(f"\n=== REVIEWs pendientes ({len(reviews)}) ===")
    for key, d in reviews:
        opp = d.get("opportunity_json") or {}
        print(f"  {key[:10]}  {opp.get('participant_home','?')} vs {opp.get('participant_away','?')}"
              f"  reco={d.get('recommended_size')}  edge={d.get('edge')}  ki={opp.get('event_start_utc')}")
    print("\n=== Órdenes abiertas (live) ===")
    try:
        orders = account_tools.get_open_orders(PolymarketAccountSource())
    except AccountUnavailableError as exc:
        print(f"  (cuenta live no disponible: {exc})")
        return
    if not orders:
        print("  (ninguna)")
    for o in orders:
        print(f"  {o.order_id[:14]}  {o.side}  price={o.price}  size={o.size_shares}"
              f"  matched={o.size_matched}  {o.condition_id[:12]}…")


def cmd_approve(key: str, *, decisions: dict, client: LocalStateClient,
                broker: PolymarketBroker, tolerance: Decimal, confirm: str | None) -> None:
    match = [(k, d) for k, d in decisions.items() if k == key or k.startswith(key)]
    if len(match) != 1:
        print(f"  clave ambigua o no encontrada: {key} ({len(match)} coincidencias)")
        return
    full_key, decision = match[0]
    opp = decision.get("opportunity_json") or {}
    token = opp.get("polymarket_token_id", "")

    live_price = broker.best_ask(token) if token else None
    ok, reason = validate_placeable(decision, now=utcnow(), live_price=live_price,
                                    tolerance=tolerance)
    if not ok:
        print(f"  NO colocable: {reason}")
        return

    order = build_trade_order_from_decision(decision, live_price)
    mode = "LIVE ⚠️" if broker.live else f"DRY-RUN ({broker._blocked_reason or 'flag off'})"
    print(f"\n  ── ORDEN A COLOCAR ({mode}) ──")
    print(f"    {opp.get('participant_home','?')} vs {opp.get('participant_away','?')}  "
          f"outcome={order.outcome}")
    print(f"    token={order.token_id[:18]}…  side={order.side.value}  "
          f"precio_live={order.price}  size={order.size_usdc} USDC  shares={order.size_shares}")
    expected = f"{to_decimal(order.size_usdc):.2f}"
    if not _confirm(expected, confirm):
        print("    Confirmación incorrecta — abortado, no se colocó nada.")
        return

    result = broker.place(order)
    if result.status != "error":
        client.mark_executed(full_key, result.model_dump(mode="json"))
    print(f"    → {result.status}  order_id={result.order_id}  raw={result.raw.get('note') or result.raw.get('error') or ''}")


def cmd_cancel(order_id: str, *, broker: PolymarketBroker, confirm: str | None) -> None:
    print(f"\n  Cancelar orden {order_id}")
    if not _confirm(order_id, confirm):
        print("    Confirmación incorrecta — abortado.")
        return
    result = broker.cancel(order_id)
    print(f"    → {result.status}  {result.raw.get('response') or result.raw.get('error') or ''}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Aprobar REVIEW → colocar / cancelar órdenes.")
    ap.add_argument("--state", default="data/agent_state.json")
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--approve", metavar="KEY", default=None)
    ap.add_argument("--cancel", metavar="ORDER_ID", default=None)
    ap.add_argument("--live", action="store_true", help="intenta envío REAL (requiere env-gates)")
    ap.add_argument("--tolerance", type=float, default=0.15)
    ap.add_argument("--confirm", default=None, help="valor de confirmación (no interactivo)")
    a = ap.parse_args()

    client = LocalStateClient(a.state, bankroll_usdc=a.bankroll)
    decisions = client._state.get("decisions", {})
    broker = PolymarketBroker(live=a.live)

    if a.approve:
        cmd_approve(a.approve, decisions=decisions, client=client, broker=broker,
                    tolerance=to_decimal(a.tolerance), confirm=a.confirm)
    elif a.cancel:
        cmd_cancel(a.cancel, broker=broker, confirm=a.confirm)
    else:
        cmd_list(decisions)


if __name__ == "__main__":
    main()
