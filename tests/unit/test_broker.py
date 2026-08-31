"""Tests del broker de Polymarket: dry-run, guardas y construcción de orden."""
from decimal import Decimal

import pytest

from core.types import OrderSide, OrderType
from execution.functions.broker import PolymarketBroker, round_to_tick
from execution.schemas.trade_order import TradeOrder


def _order(**over) -> TradeOrder:
    base = dict(
        condition_id="0xabc", token_id="123", outcome="YES", side=OrderSide.BUY,
        order_type=OrderType.LIMIT, price=Decimal("0.583"), size_usdc=Decimal("20"),
        size_shares=Decimal("34"), neg_risk=True, tick_size=Decimal("0.01"),
        min_order_size=Decimal("5"),
    )
    base.update(over)
    return TradeOrder(**base)


def test_round_to_tick():
    assert round_to_tick(Decimal("0.583"), Decimal("0.01")) == Decimal("0.58")
    assert round_to_tick(Decimal("0.587"), Decimal("0.01")) == Decimal("0.59")
    assert round_to_tick(Decimal("0.5834"), Decimal("0.001")) == Decimal("0.583")


def test_dry_run_by_default():
    res = PolymarketBroker(live=False).place(_order())
    assert res.status == "dry_run"
    assert res.raw["dry_run"] is True
    assert res.raw["neg_risk"] is True
    # precio redondeado al tick (0.583 → 0.58)
    assert res.avg_price == Decimal("0.58")


def test_min_size_reject():
    res = PolymarketBroker(live=False).place(_order(size_usdc=Decimal("1")))
    assert res.status == "rejected"
    assert "min" in res.raw["reject"]


def test_live_blocked_without_env(monkeypatch):
    monkeypatch.delenv("POLYMARKET_LIVE", raising=False)
    monkeypatch.delenv("POLYMARKET_KILL_SWITCH", raising=False)
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xdeadbeef")
    b = PolymarketBroker(live=True)
    assert b.live is False
    assert b._blocked_reason == "POLYMARKET_LIVE!=1"
    # y aun pidiéndole place, sigue dry-run
    assert b.place(_order()).status == "dry_run"


def test_live_blocked_without_key(monkeypatch):
    monkeypatch.setenv("POLYMARKET_LIVE", "1")
    monkeypatch.delenv("POLYMARKET_KILL_SWITCH", raising=False)
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
    b = PolymarketBroker(live=True)
    assert b.live is False
    assert b._blocked_reason == "sin POLYMARKET_PRIVATE_KEY"


def test_kill_switch_blocks_live(monkeypatch):
    monkeypatch.setenv("POLYMARKET_LIVE", "1")
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xdeadbeef")
    monkeypatch.setenv("POLYMARKET_KILL_SWITCH", "1")
    b = PolymarketBroker(live=True)
    assert b.live is False
    assert b._blocked_reason == "kill_switch"
