from decimal import Decimal

from adapters.football.db_reader import FootballDBReader
from adapters.football.elo_loader import FootballEloAdapter
from optimization.functions.bet_sizer import size_single
from research.functions.edge_screener import calculate_edge
from research.functions.market_scanner import PolymarketMarket, find_markets
from risk.functions.evaluate import evaluate
from tournaments.registry import load_strategy_file

STRATEGY = load_strategy_file("fifa_world_cup_2026/strategies/match_winner_v1")


def _market(prob="0.40", vol="6000"):
    return PolymarketMarket(
        condition_id="cond_1", token_id="tok_1", outcome="YES",
        model_outcome="HOME_WIN", market_probability=Decimal(prob),
        volume_usdc=Decimal(vol), liquidity_usdc=Decimal("8000"),
    )


def test_find_markets_filters_low_volume():
    pred = _prediction()
    markets = find_markets(pred, STRATEGY, market_source=lambda p: [_market(vol="100")])
    assert markets == []  # volumen < min


def _prediction():
    import sqlite3
    from tests.conftest import seed_football

    conn = sqlite3.connect(":memory:")
    seed_football(conn)
    reader = FootballDBReader("fifa_world_cup_2026", connection=conn)
    return FootballEloAdapter("fifa_world_cup_2026", reader=reader).get_event_prediction("m1")


def test_calculate_edge_builds_opportunity():
    pred = _prediction()
    opp = calculate_edge(pred, _market(prob="0.40"), STRATEGY)
    assert opp is not None
    # edge = model HOME_WIN (~0.51) - 0.40 > 0
    assert opp.edge > Decimal("0")
    assert opp.strategy_id == "match_winner_v1"
    assert opp.polymarket_condition_id == "cond_1"


def test_calculate_edge_none_when_no_model_outcome():
    pred = _prediction()
    m = _market()
    m = m.model_copy(update={"model_outcome": "NONEXISTENT"})
    assert calculate_edge(pred, m, STRATEGY) is None


def test_size_single_skips_below_min(opportunity_factory, portfolio_state):
    # edge alto pero bankroll chico → size < min_bet → SKIP
    opp = opportunity_factory(model_probability="0.60", market_probability="0.50")
    v = evaluate(opp, STRATEGY, portfolio_state)
    tiny = v.model_copy(update={"recommended_size_usdc": Decimal("1")})
    out = size_single(tiny, STRATEGY)
    assert out.skipped is True
    assert out.size_usdc == Decimal("0")


def test_size_single_caps_max_bet(opportunity_factory, portfolio_state):
    opp = opportunity_factory()
    v = evaluate(opp, STRATEGY, portfolio_state)
    big = v.model_copy(update={"recommended_size_usdc": Decimal("999")})
    out = size_single(big, STRATEGY)
    assert out.size_usdc == STRATEGY.max_bet_usdc
    assert out.capped_by == "max_bet"
