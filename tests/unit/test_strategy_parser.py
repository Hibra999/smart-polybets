from decimal import Decimal

import pytest

from core.exceptions import StrategyParseError
from core.strategy import parse_strategy_md
from tournaments.registry import load_active_strategy, load_strategy_file


def test_active_strategy_is_migrated_worldcup():
    # La estrategia activa migrada de pypro_worldcup_betting (blend + Kelly).
    s = load_active_strategy("fifa_world_cup_2026")
    assert s is not None
    assert s.is_approved
    assert s.strategy_id == "match_winner_wc_v1"
    assert s.side_criterion == "blend"
    assert s.blend_weight == Decimal("0.5")
    assert s.warmup_match_no == 2
    assert s.use_bayes_filter is False
    assert s.kelly_fraction == Decimal("0.25")
    assert s.outcomes == ["HOME_WIN", "AWAY_WIN"]


def test_generic_strategy_parses():
    s = load_strategy_file("fifa_world_cup_2026/strategies/match_winner_v1")
    assert s.edge_threshold_auto == Decimal("0.08")
    assert s.outcomes == ["HOME_WIN", "DRAW", "AWAY_WIN"]
    assert {q.id for q in s.qualitative_rules} == {"QR-001", "QR-002", "QR-003"}
    # los campos nuevos toman defaults benignos en la estrategia genérica
    assert s.side_criterion == "elo"
    assert s.warmup_match_no == 1


def test_nfl_strategy_is_active_trueskill():
    # game_winner_v1 fue migrado (TrueSkill) y está approved → activo.
    s = load_active_strategy("nfl_2026")
    assert s is not None
    assert s.side_criterion == "trueskill"
    assert load_strategy_file("nfl_2026/strategies/game_winner_v1").is_approved


def test_parser_rejects_bad_status():
    text = """version: 0.1
status: bogus
tournament_id: t
sport: football
market_type: x
edge_threshold_auto: 0.08
edge_threshold_review: 0.04
edge_threshold_discard: 0.04
min_market_volume_usdc: 5000
max_hours_to_event: 24
min_hours_to_event: 1
"""
    with pytest.raises(StrategyParseError):
        parse_strategy_md(text)


def test_parser_first_value_wins():
    text = """version: 0.1
status: approved
tournament_id: t
sport: football
market_type: x
edge_threshold_auto: 0.08
edge_threshold_review: 0.04
edge_threshold_discard: 0.04
min_market_volume_usdc: 5000
max_hours_to_event: 24
min_hours_to_event: 1
"""
    s = parse_strategy_md(text)
    assert s.edge_threshold_auto == Decimal("0.08")
