"""PnL realizado por flujo de caja: ventas + redenciones - compras."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from portfolio.functions.pnl import realized_pnl_cashflow
from portfolio.schemas.account import LiveRedemption, LiveTrade

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "pnl_cashflow.json"


def _load():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    trades = [
        LiveTrade(side=t["side"], size_shares=Decimal(t["size"]), price=Decimal(t["price"]),
                  condition_id=t["condition_id"], outcome=t.get("outcome"), title=t.get("title"))
        for t in data["trades"]
    ]
    redeems = [
        LiveRedemption(condition_id=r["condition_id"], amount=Decimal(r["amount"]), title=r.get("title"))
        for r in data["redemptions"]
    ]
    return trades, redeems, Decimal(data["expected_net_pnl"])


def test_cashflow_matches_fixture():
    trades, redeems, expected = _load()
    net = realized_pnl_cashflow(trades, redeems)
    assert net.quantize(Decimal("0.01")) == expected


def test_cashflow_includes_early_sale():
    trades, redeems, _ = _load()
    net = realized_pnl_cashflow(trades, redeems)
    assert net.quantize(Decimal("0.01")) != Decimal("-4.00")


def test_empty_is_zero():
    assert realized_pnl_cashflow([], []) == Decimal("0")
