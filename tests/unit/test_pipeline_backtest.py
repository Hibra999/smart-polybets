from datetime import UTC, datetime

from adapters.american_football.nfl_pipeline import NFLPipeline
from agent.workflows.pipeline_backtest import AWAY, HOME, simulate_games
from tournaments.registry import load_active_strategy


def _game(market_home: float, winner: str = HOME) -> dict:
    return {
        "id": "game-1",
        "home": "H",
        "away": "A",
        "home_score": 24 if winner == HOME else 10,
        "away_score": 24 if winner == AWAY else 10,
        "winner": winner,
        "kickoff_utc": datetime(2025, 10, 1, tzinfo=UTC),
        "phase": "regular_season",
        "market_home": market_home,
        "market_away": 1 - market_home,
        "target": True,
    }


def _warmed_pipeline() -> NFLPipeline:
    pipeline = NFLPipeline()
    for index in range(8):
        pipeline.process_match("H", f"X{index}", 24, 10)
        pipeline.process_match("A", f"Y{index}", 10, 24)
    return pipeline


def test_pipeline_backtest_places_only_auto_and_settles_bankroll():
    strategy = load_active_strategy("nfl_2026")
    assert strategy is not None

    result = simulate_games(
        "nfl_2026",
        [_game(0.50)],
        _warmed_pipeline(),
        strategy,
        bankroll=1000,
        price_source="test",
    )

    assert result["decisions"]["AUTO"] == 1
    assert result["performance"]["bets"] == 1
    assert result["performance"]["bankroll_final"] > 1000


def test_pipeline_backtest_does_not_bet_review_zone():
    strategy = load_active_strategy("nfl_2026")
    assert strategy is not None
    probability = _warmed_pipeline().prematch("H", "A")["ts_home"]

    result = simulate_games(
        "nfl_2026",
        [_game(probability - 0.01)],
        _warmed_pipeline(),
        strategy,
        bankroll=1000,
        price_source="test",
    )

    assert result["decisions"]["REVIEW"] == 1
    assert result["performance"]["bets"] == 0
