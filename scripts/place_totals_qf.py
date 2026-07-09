#!/usr/bin/env python
"""Colocación MANUAL de apuestas de totales (Over/Under) para los cuartos WC 2026.

Los edges de esta jornada están en los mercados de TOTALES, que la pipeline
`match_winner` (place_bets.py) no sabe colocar. Este script construye las órdenes
CLOB directamente contra los token_id de cada mercado O/U y las envía por el mismo
broker (PolymarketGateway) con los mismos gates de seguridad.

SEGURO POR DEFECTO: dry-run. Envío real requiere --live + POLYMARKET_LIVE=1 + key.

    python scripts/place_totals_qf.py            # dry-run
    python scripts/place_totals_qf.py --live     # real (con env-gates)
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

from core.types import OrderSide, OrderType
from core.utils import to_decimal
from execution.functions.broker import PolymarketBroker
from execution.schemas.trade_order import TradeOrder
from venue.discovery import match_events

# (question, side_label, outcome_key, stake_usdc)  — outcome_key: 'yes'=Over, 'no'=Under
TARGETS = [
    ("Argentina vs. Switzerland: O/U 2.5", "OVER 2.5",  "yes", Decimal("22")),
    ("Norway vs. England: O/U 2.5",        "OVER 2.5",  "yes", Decimal("22")),
    ("Spain vs. Belgium: O/U 2.5",         "UNDER 2.5", "no",  Decimal("14")),
]


def find_markets() -> dict:
    wanted = {q for q, *_ in TARGETS}
    out = {}
    for me in match_events(closed=False):
        for m in me.event.markets:
            d = m.model_dump()
            q = d.get("question") or ""
            if q in wanted and q not in out:
                out[q] = d
    return out


def run(live: bool) -> None:
    broker = PolymarketBroker(live=live)
    mode = "LIVE ⚠️" if broker.live else f"DRY-RUN ({broker._blocked_reason or 'flag off'})"
    print(f"\n=== Totales cuartos WC — modo: {mode} ===\n")

    mkts = find_markets()
    total_cost = Decimal("0")
    for q, side_label, okey, stake in TARGETS:
        d = mkts.get(q)
        if not d:
            print(f"  [MISS] no encontrado: {q}")
            continue
        o = (d.get("outcomes") or {}).get(okey, {})
        token = o.get("token_id")
        trading = d.get("trading") or {}
        # Tick real del CLOB para estos mercados (0.0025). El SDK lo re-consulta al
        # servidor de todos modos; lo usamos aquí para que el ask no se redondee mal.
        tick = to_decimal(trading.get("minimum_tick_size") or "0.001")
        min_sz = to_decimal(trading.get("minimum_order_size") or "0")

        ask = broker.best_ask(token)
        price = ask if ask is not None else to_decimal(o.get("price"))
        shares = (stake / price).quantize(Decimal("0.01"))
        order = TradeOrder(
            condition_id=d.get("condition_id"), token_id=token,
            outcome=side_label, side=OrderSide.BUY, order_type=OrderType.LIMIT,
            price=price, size_usdc=stake, size_shares=shares,
            tif="GTC", tick_size=tick, min_order_size=min_sz or None,
        )
        print(f"  {q.split(':')[0]:26} {side_label:10} "
              f"ask={price}  stake=${stake}  shares={shares}  (tick {tick})")
        res = broker.place(order)
        print(f"      -> {res.status}  order_id={res.order_id}  "
              f"{res.raw.get('note') or res.raw.get('error') or res.raw.get('response','')[:60]}")
        total_cost += stake
    print(f"\n  Total comprometido: ${total_cost}")
    if not broker.live:
        print("  (dry-run: nada se envió. Real: --live + POLYMARKET_LIVE=1)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    run(ap.parse_args().live)


if __name__ == "__main__":
    main()
