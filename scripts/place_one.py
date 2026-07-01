#!/usr/bin/env python
"""Coloca UNA orden manual sobre un fixture/lado (test). Usa precio live de Gamma.

    POLYMARKET_LIVE=1 python scripts/place_one.py --fixture wc_81 --side HOME_WIN --usd 10 --live

Dry-run salvo --live (y env POLYMARKET_LIVE=1 + key). Es una orden MANUAL: no pasa
por el gate AUTO/REVIEW (lo aprueba el humano explícitamente al correr esto).
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from core.types import OrderSide, OrderType
from execution.functions import PolymarketBroker
from execution.schemas.trade_order import TradeOrder
from research.functions import PolymarketLiveSource, get_event_prediction

TID = "fifa_world_cup_2026"


def run(fixture: str, side: str, usd: float, live: bool) -> None:
    pred = get_event_prediction(fixture, TID)
    if pred is None:
        print(f"[ERROR] sin predicción para {fixture}")
        return
    markets = PolymarketLiveSource()(pred)
    mkt = next((m for m in markets if m.model_outcome == side), None)
    if mkt is None:
        print(f"[ERROR] sin mercado live para {side} en {fixture}")
        return

    team = pred.participant_home if side == "HOME_WIN" else pred.participant_away
    price = mkt.best_ask or mkt.market_probability
    order = TradeOrder(
        condition_id=mkt.condition_id, token_id=mkt.token_id, outcome="YES",
        side=OrderSide.BUY, order_type=OrderType.LIMIT, price=price,
        size_usdc=Decimal(str(usd)), size_shares=Decimal(str(usd)) / price,
        neg_risk=mkt.neg_risk, tick_size=mkt.tick_size, min_order_size=mkt.min_order_size,
    )

    print(f"Partido: {pred.participant_home} vs {pred.participant_away}")
    print(f"Comprando '{team} gana' (YES) por {usd} pUSD")
    print(f"  token_id : {mkt.token_id}")
    print(f"  best_ask : {price}  (mid {mkt.market_probability})  tick {mkt.tick_size}  neg_risk {mkt.neg_risk}")
    print(f"  shares   : ~{float(Decimal(str(usd)) / price):.2f}")

    broker = PolymarketBroker(live=live)
    print(f"  modo broker: {'LIVE' if broker.live else 'DRY-RUN (' + str(broker._blocked_reason) + ')'}")
    res = broker.place(order)
    print(f"\nRESULTADO: status={res.status}  order_id={res.order_id}")
    print(f"  avg_price={res.avg_price}  filled={res.filled_size_usdc}")
    if res.raw.get("response"):
        print(f"  response: {res.raw['response']}")
    if res.raw.get("error"):
        print(f"  error: {res.raw['error']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--side", default="HOME_WIN", choices=["HOME_WIN", "AWAY_WIN"])
    ap.add_argument("--usd", type=float, default=10.0)
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    run(a.fixture, a.side, a.usd, a.live)


if __name__ == "__main__":
    main()
