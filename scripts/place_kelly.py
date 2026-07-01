#!/usr/bin/env python
"""Coloca las apuestas accionables del día sizeadas por Kelly sobre el bankroll real.

- Lee el bankroll de los fondos pUSD (o --bankroll).
- Computa el stake Kelly de cada pick accionable (edge>0, AUTO/REVIEW).
- Descuenta lo ya invertido en cada mercado (posición existente) → coloca solo el
  TOP-UP necesario para llegar al tamaño Kelly.
- Dry-run salvo --live (+ POLYMARKET_LIVE=1 + key).

    POLYMARKET_LIVE=1 python scripts/place_kelly.py --date 2026-06-20 --live
"""
from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from adapters.football import FootballDBReader
from core.types import OrderSide, OrderType
from execution.functions import PolymarketBroker
from execution.schemas.trade_order import TradeOrder
from research.functions import PolymarketLiveSource, get_event_prediction, pick_side
from risk.functions.kelly import fractional_kelly
from tournaments.registry import load_active_strategy

TID = "fifa_world_cup_2026"
MIN_BET = Decimal("5")


def _sdk():
    import polymarket as P
    return P.SecureClient.create(private_key=os.environ["POLYMARKET_PRIVATE_KEY"]), P


def _read_bankroll(client) -> Decimal:
    ba = client.get_balance_allowance(asset_type="COLLATERAL")
    return Decimal(int(ba.balance)) / Decimal("1000000")


def _shares_held(client, token_id: str) -> Decimal:
    try:
        ba = client.get_balance_allowance(asset_type="CONDITIONAL", token_id=token_id)
        return Decimal(int(ba.balance)) / Decimal("1000000")
    except Exception:
        return Decimal("0")


def run(date: str, bankroll_override: float | None, live: bool,
        only: list[str] | None = None) -> None:
    client, _ = _sdk()
    bankroll = Decimal(str(bankroll_override)) if bankroll_override else _read_bankroll(client)
    print(f"Bankroll (pUSD): {bankroll:.2f}\n")

    strat = load_active_strategy(TID)
    src = PolymarketLiveSource()
    reader = FootballDBReader(TID)
    fixtures = reader.query(
        "SELECT id FROM fixture WHERE status='scheduled' AND kickoff_utc LIKE ? ORDER BY kickoff_utc",
        (f"{date}%",),
    )
    if only:
        keep = set(only)
        fixtures = [f for f in fixtures if f["id"] in keep]
        print(f"Filtro --only: {sorted(keep)}\n")

    broker = PolymarketBroker(live=live)
    print(f"Modo: {'LIVE' if broker.live else 'DRY-RUN (' + str(broker._blocked_reason) + ')'}")
    print("(sizing Kelly directo; se omite la ventana horaria por ser colocación manual)\n")

    for f in fixtures:
        pred = get_event_prediction(f["id"], TID)
        if pred is None:
            continue
        markets = src(pred)
        pk = pick_side(pred, strat.side_criterion, strat.blend_weight)
        side, model_prob = pk["side"], Decimal(str(pk["model_prob"]))
        team = pred.participant_home if side == "HOME_WIN" else pred.participant_away
        mkt = next((m for m in markets if m.model_outcome == side), None)
        if mkt is None:
            continue
        mid = mkt.market_probability
        ask = mkt.best_ask or mid
        edge = model_prob - mid
        if edge <= 0:   # sin valor sobre el mercado
            continue

        kelly = fractional_kelly(model_prob, mid, strat.kelly_fraction, bankroll,
                                 max_bet_usdc=strat.max_bet_usdc,
                                 max_kelly_fraction=strat.max_kelly_fraction)
        target = kelly.recommended_size_usdc
        held = _shares_held(client, mkt.token_id)
        existing = held * ask
        topup = target - existing

        print(f"  {team:14} edge {float(edge)*100:+.1f}%  modelo {float(model_prob)*100:.0f}% vs "
              f"mercado {float(mid)*100:.0f}%  Kelly=${target:.2f}  ya=${existing:.2f} "
              f"({held:.1f} sh)  top-up=${max(topup,Decimal('0')):.2f}")

        if topup < MIN_BET:
            print("     -> nada que agregar (top-up < $5)"); continue

        order = TradeOrder(
            condition_id=mkt.condition_id, token_id=mkt.token_id, outcome="YES",
            side=OrderSide.BUY, order_type=OrderType.LIMIT, price=ask,
            size_usdc=topup, size_shares=topup / ask,
            neg_risk=mkt.neg_risk, tick_size=mkt.tick_size, min_order_size=mkt.min_order_size,
        )
        res = broker.place(order)
        tag = res.raw.get("response") or res.raw.get("error") or res.raw.get("note", "")
        print(f"     -> {res.status}  id={res.order_id[:24]}  {str(tag)[:90]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-06-20")
    ap.add_argument("--bankroll", type=float, default=None, help="override; si no, lee pUSD")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--only", nargs="+", default=None, help="solo estos fixture ids")
    a = ap.parse_args()
    run(a.date, a.bankroll, a.live, only=a.only)


if __name__ == "__main__":
    main()
