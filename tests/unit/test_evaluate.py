from decimal import Decimal

from risk.functions.evaluate import evaluate
from tournaments.registry import load_strategy_file

# Estrategia genérica 3-way (thresholds 0.08/0.04/0.04) — estable para probar la
# lógica de evaluate independientemente de cuál sea la estrategia activa.
STRATEGY = load_strategy_file("liga_mx_2026/strategies/match_winner_ligamx_v1")


def test_auto_verdict(opportunity_factory, portfolio_state):
    opp = opportunity_factory(model_probability="0.60", market_probability="0.50")  # edge 0.10
    v = evaluate(opp, STRATEGY, portfolio_state)
    assert v.verdict.value == "AUTO"
    assert v.recommended_size_usdc > 0
    assert v.blocking_rules == []


def test_review_zone_edge(opportunity_factory, portfolio_state):
    opp = opportunity_factory(model_probability="0.56", market_probability="0.50")  # edge 0.06
    v = evaluate(opp, STRATEGY, portfolio_state)
    assert v.verdict.value == "REVIEW"


def test_discard_low_edge(opportunity_factory, portfolio_state):
    opp = opportunity_factory(model_probability="0.49", market_probability="0.50")
    v = evaluate(opp, STRATEGY, portfolio_state)
    assert v.verdict.value == "DISCARD"
    assert v.recommended_size_usdc == Decimal("0")
    assert any("edge" in r for r in v.blocking_rules)


def test_discard_low_volume(opportunity_factory, portfolio_state):
    opp = opportunity_factory(market_volume_usdc="100")  # < 5000
    v = evaluate(opp, STRATEGY, portfolio_state)
    assert v.verdict.value == "DISCARD"


def test_qualitative_flag_forces_review(opportunity_factory, portfolio_state):
    opp = opportunity_factory(model_probability="0.60", market_probability="0.50")  # AUTO-able
    v = evaluate(opp, STRATEGY, portfolio_state, qualitative_flags=["QR-002: lesión"])
    assert v.verdict.value == "REVIEW"
    assert "QR-002: lesión" in v.qualitative_flags


def test_liguilla_phase_forces_review(opportunity_factory, portfolio_state):
    opp = opportunity_factory(event_phase="liguilla")
    v = evaluate(opp, STRATEGY, portfolio_state)
    assert v.verdict.value == "REVIEW"


def test_low_confidence_forces_review(opportunity_factory, portfolio_state):
    opp = opportunity_factory(model_confidence="LOW")
    v = evaluate(opp, STRATEGY, portfolio_state)
    assert v.verdict.value == "REVIEW"
