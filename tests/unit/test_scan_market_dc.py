"""Tests for _bet_row helper in scan_market — double_chance + win mode."""
from decimal import Decimal
import scripts.scan_market as sm
from research.functions.market_scanner import PolymarketMarket
from core.strategy import StrategyConfig


def _strat(bt): return StrategyConfig(version="1", status="approved", tournament_id="t",
    sport="football", market_type="match_winner", bet_type=bt,
    edge_threshold_auto=Decimal("0.05"), edge_threshold_review=Decimal("0.03"),
    edge_threshold_discard=Decimal("0.00"), min_market_volume_usdc=Decimal("1000"),
    max_hours_to_event=48.0, min_hours_to_event=0.5)


def test_bet_row_double_chance():
    markets = [PolymarketMarket(condition_id="c", token_id="Yh", outcome="YES",
                 model_outcome="HOME_WIN", market_probability=Decimal("0.6"),
                 volume_usdc=Decimal("1"), liquidity_usdc=Decimal("1")),
               PolymarketMarket(condition_id="c", token_id="Ya", outcome="YES",
                 model_outcome="AWAY_WIN", market_probability=Decimal("0.25"),
                 volume_usdc=Decimal("1"), liquidity_usdc=Decimal("1"),
                 no_token_id="Na", no_probability=Decimal("0.72"), no_best_ask=Decimal("0.73"))]
    pr = {"home": 0.55, "draw": 0.25, "away": 0.20}
    row = sm._bet_row("HOME_WIN", Decimal("0.6"), markets, _strat("double_chance"), pr)
    assert row is not None
    outcome, model_prob, market_prob, edge = row
    assert outcome == "NO"
    assert abs(float(model_prob) - 0.80) < 1e-9         # P(home)+P(draw)
    assert market_prob == Decimal("0.72")
    assert abs(float(edge) - 0.08) < 1e-9               # 0.80 - 0.72


def test_bet_row_win_mode():
    """win mode: returns YES market of the picked side, same edge as old inline code."""
    markets = [PolymarketMarket(condition_id="c", token_id="Yh", outcome="YES",
                 model_outcome="HOME_WIN", market_probability=Decimal("0.55"),
                 volume_usdc=Decimal("1"), liquidity_usdc=Decimal("1")),
               PolymarketMarket(condition_id="c", token_id="Ya", outcome="YES",
                 model_outcome="AWAY_WIN", market_probability=Decimal("0.30"),
                 volume_usdc=Decimal("1"), liquidity_usdc=Decimal("1"))]
    row = sm._bet_row("HOME_WIN", Decimal("0.65"), markets, _strat("win"), None)
    assert row is not None
    outcome, model_prob, market_prob, edge = row
    assert outcome == "YES"
    assert model_prob == Decimal("0.65")
    assert market_prob == Decimal("0.55")
    assert abs(float(edge) - 0.10) < 1e-9


def test_bet_row_returns_none_when_no_market():
    """Returns None if there's no matching market for the given side."""
    markets = [PolymarketMarket(condition_id="c", token_id="Ya", outcome="YES",
                 model_outcome="AWAY_WIN", market_probability=Decimal("0.30"),
                 volume_usdc=Decimal("1"), liquidity_usdc=Decimal("1"))]
    row = sm._bet_row("HOME_WIN", Decimal("0.65"), markets, _strat("win"), None)
    assert row is None


def test_bet_row_double_chance_returns_none_without_poisson():
    """double_chance mode requires poisson_result; None poisson → None row."""
    markets = [PolymarketMarket(condition_id="c", token_id="Yh", outcome="YES",
                 model_outcome="HOME_WIN", market_probability=Decimal("0.6"),
                 volume_usdc=Decimal("1"), liquidity_usdc=Decimal("1")),
               PolymarketMarket(condition_id="c", token_id="Ya", outcome="YES",
                 model_outcome="AWAY_WIN", market_probability=Decimal("0.25"),
                 volume_usdc=Decimal("1"), liquidity_usdc=Decimal("1"),
                 no_token_id="Na", no_probability=Decimal("0.72"))]
    row = sm._bet_row("HOME_WIN", Decimal("0.6"), markets, _strat("double_chance"), None)
    assert row is None


def test_registry_has_scan_tags_for_registered_markets():
    assert sm.get_config("liga_mx_2026").polymarket_tag_id == 102448
    assert sm.get_config("fifa_world_cup_2026").polymarket_tag_id == 102232
    assert sm.get_config("nfl_2026").polymarket_tag_id == 450
