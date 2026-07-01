from decimal import Decimal

import pytest

from core.utils import make_idempotency_key, quantize_usdc, redact_wallet
from research.schemas.market_opportunity import MarketOpportunity


def test_idempotency_key_deterministic():
    a = make_idempotency_key("c", "YES", "s", "0.1", "2026-06-19")
    b = make_idempotency_key("c", "YES", "s", "0.1", "2026-06-19")
    c = make_idempotency_key("c", "NO", "s", "0.1", "2026-06-19")
    assert a == b
    assert a != c
    assert len(a) == 64


def test_quantize_usdc():
    assert quantize_usdc("10.005") == Decimal("10.01")
    assert quantize_usdc(10) == Decimal("10.00")


def test_redact_wallet():
    assert redact_wallet("0x1234567890abcdef") == "0x1234...cdef"
    assert redact_wallet("short") == "0x????"


def test_opportunity_idempotency_key_property(opportunity_factory):
    opp = opportunity_factory()
    assert len(opp.idempotency_key) == 64


def test_opportunity_edge_out_of_range():
    with pytest.raises(Exception):
        MarketOpportunity(
            polymarket_condition_id="c", polymarket_token_id="t", outcome="YES",
            tournament_id="t", sport="football", event_id="e", market_type="x",
            strategy_id="s", model_probability=Decimal("0.5"),
            market_probability=Decimal("0.5"), edge=Decimal("2"),  # fuera de rango
            participant_home="a", participant_away="b",
            event_start_utc="2026-06-19T00:00:00+00:00", hours_to_event=5,
            event_phase="group", market_volume_usdc=Decimal("1"),
            market_liquidity_usdc=Decimal("1"), model_version="v",
            model_confidence="HIGH", sample_size=1,
            generated_at="2026-06-19T00:00:00+00:00", strategy_version="0.1",
        )
