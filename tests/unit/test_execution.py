from decimal import Decimal

import pytest

from core.exceptions import AgentError
from execution.functions.order_builder import build_order
from execution.functions.order_classifier import classify
from execution.functions.price_validator import validate_live_price
from execution.functions.slippage_estimator import estimate
from execution.functions.submit import submit_order
from risk.functions.evaluate import evaluate
from agent.tools import execution_tools
from tournaments.registry import load_active_strategy

STRATEGY = load_active_strategy("fifa_world_cup_2026")


def test_price_validator():
    assert validate_live_price(0.50, 0.51, Decimal("0.05")) is True
    assert validate_live_price(0.50, 0.60, Decimal("0.05")) is False


def test_slippage_no_orderbook():
    est = estimate("tok", 100)
    assert est.slippage_pct == Decimal("0")
    assert est.fully_filled is False


def test_slippage_with_orderbook():
    est = estimate("tok", 100, orderbook=[(0.50, 50), (0.52, 100)])
    assert est.fully_filled is True
    assert est.expected_avg_price > Decimal("0.50")


def test_auto_order_classified_no_approval(opportunity_factory, portfolio_state):
    v = evaluate(opportunity_factory(), STRATEGY, portfolio_state)
    order = build_order(v)
    decision = classify(order, v)
    assert decision.requires_approval is False
    assert decision.idempotency_key == v.opportunity.idempotency_key


def test_review_order_requires_approval(opportunity_factory, portfolio_state):
    v = evaluate(opportunity_factory(event_phase="knockout"), STRATEGY, portfolio_state)
    order = build_order(v)
    decision = classify(order, v)
    assert decision.requires_approval is True
    assert decision.approval_deadline is not None


def test_submit_blocked_on_review(opportunity_factory, portfolio_state):
    v = evaluate(opportunity_factory(event_phase="knockout"), STRATEGY, portfolio_state)
    order = build_order(v)
    decision = classify(order, v)
    with pytest.raises(AgentError):
        execution_tools.submit(order, decision)


def test_submit_dry_run_on_auto(opportunity_factory, portfolio_state):
    v = evaluate(opportunity_factory(), STRATEGY, portfolio_state)
    order = build_order(v)
    result = submit_order(order)  # broker por defecto = dry-run
    assert result.status == "dry_run"
    assert result.order_id.startswith("ord-")
    assert result.raw["dry_run"] is True
