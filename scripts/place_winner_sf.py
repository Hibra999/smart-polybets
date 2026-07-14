#!/usr/bin/env python
"""Colocación MANUAL de apuestas de ganador para las semifinales WC 2026.

Aprobadas por el CIO el 2026-07-13 (sizing Poisson-corregido, Kelly ¼, ver
docs/findings/2026-07-13-poisson-sesgo-knockout.md):
  - Spain win  $12 @ ask ~0.300 (cap 0.315)
  - Argentina win $7 @ ask ~0.315 (cap 0.330)

Va por orden manual (no pipeline) porque el `side_criterion: blend` de la
estrategia pickearía France, y el sizing aprobado es el del yardstick Poisson,
no el Kelly-blend. ⚠️ Bypassea motor de riesgo/idempotencia/ledger local
(consistente: el PnL se lee de la cuenta live).

Cada orden es LIMIT al best_ask live, capado a `max_price`: si el mercado se
movió por encima del cap, la orden queda resting sin fill (no compramos caro).

SEGURO POR DEFECTO: dry-run. Envío real requiere --live + POLYMARKET_LIVE=1 + key.

    python scripts/place_winner_sf.py            # dry-run
    python scripts/place_winner_sf.py --live     # real (con env-gates)
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

# (question, side_label, outcome_key, stake_usdc, max_price)
TARGETS = [
    ("Will Spain win on 2026-07-14?",     "SPAIN WIN",     "yes", Decimal("12"), Decimal("0.315")),
    ("Will Argentina win on 2026-07-15?", "ARGENTINA WIN", "yes", Decimal("7"),  Decimal("0.33")),
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
    print(f"\n=== Ganador semifinales WC — modo: {mode} ===\n")

    mkts = find_markets()
    total_cost = Decimal("0")
    for q, side_label, okey, stake, cap in TARGETS:
        d = mkts.get(q)
        if not d:
            print(f"  [MISS] no encontrado: {q}")
            continue
        o = (d.get("outcomes") or {}).get(okey, {})
        token = o.get("token_id")
        trading = d.get("trading") or {}
        tick = to_decimal(trading.get("minimum_tick_size") or "0.001")
        min_sz = to_decimal(trading.get("minimum_order_size") or "0")

        ask = broker.best_ask(token)
        price = ask if ask is not None else to_decimal(o.get("price"))
        if price > cap:
            print(f"  [SKIP] {q}: ask {price} > cap {cap} — el edge aprobado ya no está")
            continue
        shares = (stake / price).quantize(Decimal("0.01"))
        order = TradeOrder(
            condition_id=d.get("condition_id"), token_id=token,
            outcome=side_label, side=OrderSide.BUY, order_type=OrderType.LIMIT,
            price=price, size_usdc=stake, size_shares=shares,
            tif="GTC", tick_size=tick, min_order_size=min_sz or None,
        )
        print(f"  {q:35} {side_label:14} "
              f"ask={price}  stake=${stake}  shares={shares}  (tick {tick}, cap {cap})")
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
