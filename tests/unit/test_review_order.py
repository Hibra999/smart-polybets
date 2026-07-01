from datetime import datetime, timezone
from decimal import Decimal

from core.types import OrderSide, OrderType
from execution.functions.review_order import (
    build_trade_order_from_decision,
    validate_placeable,
)

NOW = datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc)


def _decision(**over):
    opp = {
        "polymarket_token_id": "81043", "polymarket_condition_id": "0xcond",
        "outcome": "YES", "best_ask": "0.58", "market_probability": "0.575",
        "neg_risk": True, "tick_size": "0.01", "min_order_size": "5",
        "event_start_utc": "2026-06-20T13:00:00Z",
    }
    opp.update(over.pop("opp", {}))
    d = {"idempotency_key": "k1", "recommended_size": "50.00", "status": "pending_approval",
         "verdict": "REVIEW", "condition_id": "0xcond", "opportunity_json": opp}
    d.update(over)
    return d


def test_placeable_ok_when_fresh_and_price_close():
    ok, reason = validate_placeable(_decision(), now=NOW, live_price=Decimal("0.60"))
    assert ok is True and reason == "ok"


def test_rejects_started_event():
    late = datetime(2026, 6, 20, 14, 0, tzinfo=timezone.utc)  # después del kickoff 13:00
    ok, reason = validate_placeable(_decision(), now=late, live_price=Decimal("0.58"))
    assert ok is False and "empez" in reason.lower()


def test_rejects_missing_event_start_utc():
    # Sin timestamp del evento → no colocable (no se puede validar expiración).
    ok, reason = validate_placeable(_decision(opp={"event_start_utc": None}),
                                    now=NOW, live_price=Decimal("0.58"))
    assert ok is False and "event_start_utc" in reason.lower()


def test_rejects_missing_token():
    ok, reason = validate_placeable(_decision(opp={"polymarket_token_id": ""}),
                                    now=NOW, live_price=Decimal("0.58"))
    assert ok is False and "token" in reason.lower()


def test_rejects_no_live_price():
    ok, reason = validate_placeable(_decision(), now=NOW, live_price=None)
    assert ok is False and "repreci" in reason.lower()


def test_rejects_high_slippage():
    # señal 0.58, live 0.80 → +38% > 15%
    ok, reason = validate_placeable(_decision(), now=NOW, live_price=Decimal("0.80"))
    assert ok is False and "slippage" in reason.lower()


def test_build_trade_order_maps_fields_and_shares():
    order = build_trade_order_from_decision(_decision(), Decimal("0.50"))
    assert order.token_id == "81043"
    assert order.condition_id == "0xcond"
    assert order.side == OrderSide.BUY
    assert order.order_type == OrderType.LIMIT
    assert order.price == Decimal("0.50")
    assert order.size_usdc == Decimal("50.00")
    assert order.size_shares == Decimal("100")          # 50 / 0.50
    assert order.neg_risk is True
    assert order.tick_size == Decimal("0.01")
    assert order.min_order_size == Decimal("5")
