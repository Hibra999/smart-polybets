"""PnL por flujo de caja: debe cuadrar con la UI de Polymarket (no con el snapshot).

Regresión del bug del 2026-07-17: el método de snapshot daba -27.40 (sobreestimaba
las pérdidas por ignorar el salvamento de cierres anticipados); el flujo de caja real
da -19.58, idéntico a la UI. Ver docs/findings/2026-07-17-pnl-cashflow-vs-snapshot.md.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from portfolio.functions.pnl import realized_pnl_cashflow
from portfolio.schemas.account import LiveRedemption, LiveTrade

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "pnl_cashflow_wc2026.json"


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


def test_cashflow_matches_polymarket_ui():
    trades, redeems, expected = _load()
    net = realized_pnl_cashflow(trades, redeems)
    # cuadra con la UI de Polymarket (-19.58) al centavo
    assert net.quantize(Decimal("0.01")) == expected


def test_cashflow_differs_from_snapshot_by_salvage():
    """El flujo de caja NO es la suma naïve; el salvamento de las 5 ventas lo separa
    del método de snapshot (-27.40)."""
    trades, redeems, _ = _load()
    net = realized_pnl_cashflow(trades, redeems)
    assert net.quantize(Decimal("0.01")) != Decimal("-27.40")


def test_empty_is_zero():
    assert realized_pnl_cashflow([], []) == Decimal("0")
