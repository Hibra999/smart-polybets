#!/usr/bin/env python
"""Coloca apuestas Over (mercado de goles) sizeadas por Kelly: Poisson vs Polymarket.

Para cada fixture pasado: trae el mercado "{H} vs. {A}: O/U {line}" (outcome Over),
computa P(Over) con el modelo Poisson, el edge vs el mid del mercado y el stake Kelly
(mismos parámetros que la estrategia activa). Descuenta posición existente (top-up).

Dry-run salvo --live (+ POLYMARKET_LIVE=1 + key). Es colocación MANUAL del CIO sobre
un modelo aún no validado contra la línea: úsese con criterio.

    POLYMARKET_LIVE=1 python scripts/place_over.py --fixtures wc_93 wc_94 --line 2.5 --live
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
from adapters.football.wc_poisson_pipeline import WorldCupPoissonPipeline
from core.types import OrderSide, OrderType
from execution.functions import PolymarketBroker
from execution.schemas.trade_order import TradeOrder
from research.functions.polymarket_goals import fetch_goals_market
from risk.functions.kelly import fractional_kelly
from tournaments.registry import load_active_strategy

TID = "fifa_world_cup_2026"
MIN_BET = Decimal("5")


def _sdk():
    import polymarket as P
    return P.SecureClient.create(private_key=os.environ["POLYMARKET_PRIVATE_KEY"])


def _read_bankroll(client) -> Decimal:
    ba = client.get_balance_allowance(asset_type="COLLATERAL")
    return Decimal(int(ba.balance)) / Decimal("1000000")


def _shares_held(client, token_id: str) -> Decimal:
    try:
        ba = client.get_balance_allowance(asset_type="CONDITIONAL", token_id=token_id)
        return Decimal(int(ba.balance)) / Decimal("1000000")
    except Exception:  # noqa: BLE001
        return Decimal("0")


def run(fixture_ids: list[str], line: float, bankroll_override: float | None, live: bool) -> None:
    client = _sdk()
    bankroll = Decimal(str(bankroll_override)) if bankroll_override else _read_bankroll(client)
    print(f"Bankroll (pUSD): {bankroll:.2f}  | linea O/U {line:g}  | outcome Over\n")

    strat = load_active_strategy(TID)
    reader = FootballDBReader(TID)
    pipe = WorldCupPoissonPipeline(TID).fit()
    broker = PolymarketBroker(live=live)
    print(f"Modo: {'LIVE' if broker.live else 'DRY-RUN (' + str(broker._blocked_reason) + ')'}\n")

    for fid in fixture_ids:
        fx = reader.get_fixture(fid)
        if fx is None:
            print(f"  {fid}: fixture no encontrado"); continue
        home, away = fx["home_team_id"], fx["away_team_id"]
        gm = fetch_goals_market(home, away, kind="ou", line=line, outcome="Over")
        if gm is None or not gm.accepting_orders:
            print(f"  {home} vs {away}: sin mercado Over {line:g} aceptando ordenes"); continue

        model_p = Decimal(str(pipe.forecast(home, away).prob_over(line)))
        mid = gm.price
        ask = gm.best_ask or mid
        edge = model_p - mid
        kelly = fractional_kelly(model_p, mid, strat.kelly_fraction, bankroll,
                                 max_bet_usdc=strat.max_bet_usdc,
                                 max_kelly_fraction=strat.max_kelly_fraction)
        target = kelly.recommended_size_usdc if edge > 0 else Decimal("0")
        held = _shares_held(client, gm.token_id)
        existing = held * ask
        topup = target - existing

        print(f"  {home} vs {away}  Over {line:g}: modelo {float(model_p)*100:.1f}% vs "
              f"mercado {float(mid)*100:.1f}%  edge {float(edge)*100:+.1f}%")
        print(f"     Kelly=${target:.2f}  ya=${existing:.2f} ({held:.1f} sh)  "
              f"top-up=${max(topup, Decimal('0')):.2f}  @ ask {ask}")
        if edge <= 0:
            print("     -> sin edge sobre el mercado, no se coloca"); continue
        if topup < MIN_BET:
            print("     -> top-up < $5, nada que agregar"); continue

        order = TradeOrder(
            condition_id=gm.condition_id, token_id=gm.token_id, outcome="YES",
            side=OrderSide.BUY, order_type=OrderType.LIMIT, price=ask,
            size_usdc=topup, size_shares=topup / ask,
            neg_risk=gm.neg_risk, tick_size=gm.tick_size, min_order_size=gm.min_order_size,
        )
        res = broker.place(order)
        tag = res.raw.get("response") or res.raw.get("error") or res.raw.get("note", "")
        print(f"     -> {res.status}  id={res.order_id[:24]}  {str(tag)[:90]}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", nargs="+", required=True)
    ap.add_argument("--line", type=float, default=2.5)
    ap.add_argument("--bankroll", type=float, default=None)
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    run(a.fixtures, a.line, a.bankroll, a.live)


if __name__ == "__main__":
    main()
