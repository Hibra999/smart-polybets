from decimal import Decimal

from execution.functions.broker import PolymarketBroker


def test_cancel_dry_run_when_not_live(monkeypatch):
    monkeypatch.delenv("POLYMARKET_LIVE", raising=False)
    broker = PolymarketBroker(live=False)
    res = broker.cancel("ord-123")
    assert res.status == "dry_run"
    assert res.order_id == "ord-123"
    assert res.filled_size_usdc == Decimal("0")
    assert res.raw.get("action") == "cancel"


def test_best_ask_returns_none_without_client(monkeypatch):
    # Sin key ni SDK utilizable, best_ask degrada a None (no rompe).
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
    broker = PolymarketBroker(live=False, private_key="")
    assert broker.best_ask("0xtoken") is None
