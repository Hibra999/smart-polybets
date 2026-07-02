from decimal import Decimal
from research.functions.wc_strategy import resolve_bet_market, HOME_WIN, AWAY_WIN
from research.functions.market_scanner import PolymarketMarket
from core.strategy import StrategyConfig

def _mk(model_outcome, yes_prob, no_token="N", no_prob="0.0", no_ask="0.0"):
    return PolymarketMarket(
        condition_id="c", token_id="Y"+model_outcome, outcome="YES",
        model_outcome=model_outcome, market_probability=Decimal(yes_prob),
        volume_usdc=Decimal("100"), liquidity_usdc=Decimal("50"),
        no_token_id=no_token, no_probability=Decimal(no_prob), no_best_ask=Decimal(no_ask))

def _strat(bet_type):
    return StrategyConfig(version="1", status="approved", tournament_id="t",
                          sport="football", market_type="match_winner", bet_type=bet_type,
                          edge_threshold_auto=Decimal("0.05"),
                          edge_threshold_review=Decimal("0.03"),
                          edge_threshold_discard=Decimal("0.00"),
                          min_market_volume_usdc=Decimal("1000"),
                          max_hours_to_event=48.0,
                          min_hours_to_event=0.5)

MARKETS = [_mk(HOME_WIN, "0.60"), _mk(AWAY_WIN, "0.25", no_token="No_away",
                                     no_prob="0.75", no_ask="0.76")]

def test_win_mode_picks_own_yes_market():
    t = resolve_bet_market(HOME_WIN, Decimal("0.60"), MARKETS, _strat("win"), None)
    assert t.market.model_outcome == HOME_WIN and t.market.outcome == "YES"
    assert t.model_probability == Decimal("0.60")

def test_double_chance_picks_opponent_no_market():
    # pick=HOME, rival=AWAY → compramos el NO del mercado AWAY
    pr = {"home": 0.55, "draw": 0.25, "away": 0.20}
    t = resolve_bet_market(HOME_WIN, Decimal("0.60"), MARKETS, _strat("double_chance"), pr)
    assert t.market.outcome == "NO"
    assert t.market.token_id == "No_away"
    assert t.market.model_outcome == HOME_WIN          # el NO resuelve a favor del pick
    # model_prob = P(home)+P(draw) = 0.80
    assert abs(float(t.model_probability) - 0.80) < 1e-9

def test_double_chance_skips_without_poisson():
    assert resolve_bet_market(HOME_WIN, Decimal("0.6"), MARKETS, _strat("double_chance"), None) is None

def test_double_chance_skips_without_no_token():
    mk = [_mk(HOME_WIN, "0.60"), PolymarketMarket(condition_id="c", token_id="Ya",
           outcome="YES", model_outcome=AWAY_WIN, market_probability=Decimal("0.25"),
           volume_usdc=Decimal("1"), liquidity_usdc=Decimal("1"))]  # sin no_token_id
    pr = {"home": 0.55, "draw": 0.25, "away": 0.20}
    assert resolve_bet_market(HOME_WIN, Decimal("0.6"), mk, _strat("double_chance"), pr) is None
