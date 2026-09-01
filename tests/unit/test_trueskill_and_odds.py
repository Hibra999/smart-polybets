"""Tests del port de TrueSkill y de la fuente de cuotas reales (SqliteOddsSource)."""
import sqlite3
from decimal import Decimal

import pytest

from adapters.football.trueskill import TrueSkillSystem
from core.types import ModelConfidence
from core.utils import utcnow
from research.functions.odds_source import SqliteOddsSource
from research.functions.strategy_selection import pick_side
from research.schemas.match_prediction import MatchPrediction


# ── TrueSkill (validado contra la lib `trueskill` del repo origen) ───────────


def test_trueskill_seed():
    ts = TrueSkillSystem()
    ts.seed_from_elo({"A": 1700, "B": 1500})
    # mu = 25 + (1700-1500)/40 = 30 ; sigma = 25/3
    assert ts.get("A").mu == pytest.approx(30.0)
    assert ts.get("A").sigma == pytest.approx(25 / 3)


def test_trueskill_win_probability_reference():
    ts = TrueSkillSystem()
    ts.seed_from_elo({"A": 1700, "B": 1500})
    # valor de referencia de la librería trueskill: 0.647832
    assert ts.win_probability("A", "B") == pytest.approx(0.647832, abs=1e-5)


def test_trueskill_symmetric():
    ts = TrueSkillSystem()
    ts.seed_from_elo({"A": 1650, "B": 1500})
    assert ts.win_probability("A", "B") + ts.win_probability("B", "A") == pytest.approx(1.0)


def test_trueskill_update_after_win():
    ts = TrueSkillSystem()
    ts.seed_from_elo({"A": 1700, "B": 1500})
    ts.update_match("A", "B", 2, 0)
    # referencia lib: A μ=33.462083 σ=7.297199 ; winprob_post=0.842169
    assert ts.get("A").mu == pytest.approx(33.462083, abs=1e-4)
    assert ts.get("A").sigma == pytest.approx(7.297199, abs=1e-4)
    assert ts.win_probability("A", "B") == pytest.approx(0.842169, abs=1e-5)


def test_trueskill_draw_keeps_means_close():
    ts = TrueSkillSystem()
    ts.seed_from_elo({"A": 1600, "B": 1500})
    ts.update_match("A", "B", 1, 1)
    # referencia lib: A μ=26.507299, B μ=25.992701 (sigma baja por igual)
    assert ts.get("A").mu == pytest.approx(26.507299, abs=1e-4)
    assert ts.get("B").mu == pytest.approx(25.992701, abs=1e-4)


def _prediction_with_ts() -> MatchPrediction:
    return MatchPrediction(
        event_id="m1", tournament_id="t", sport="football", market_type="match_winner",
        participant_home="A", participant_away="B", event_start_utc=utcnow(),
        event_phase="group",
        probabilities={"HOME_WIN": Decimal("0.55"), "AWAY_WIN": Decimal("0.45")},
        components={
            "elo": {"HOME_WIN": Decimal("0.55"), "AWAY_WIN": Decimal("0.45")},
            "bayes": {"HOME_WIN": Decimal("0.60"), "AWAY_WIN": Decimal("0.50")},
            "trueskill": {"HOME_WIN": Decimal("0.40"), "AWAY_WIN": Decimal("0.60")},
        },
        appearances={"HOME_WIN": 2, "AWAY_WIN": 2},
        model_version="football", model_confidence=ModelConfidence.MEDIUM, sample_size=2,
        generated_at=utcnow(),
    )


def test_pick_side_trueskill_uses_ts_component():
    pred = _prediction_with_ts()
    # Elo favorece HOME (0.55) pero TrueSkill favorece AWAY (0.60)
    assert pick_side(pred, "elo", Decimal("0.5"))["side"] == "HOME_WIN"
    ts_pick = pick_side(pred, "trueskill", Decimal("0.5"))
    assert ts_pick["side"] == "AWAY_WIN"
    # p_pick (sizing) usa la prob TrueSkill del lado elegido
    assert ts_pick["model_prob"] == Decimal("0.60")


# ── SqliteOddsSource (cuotas reales migradas) ────────────────────────────────


def _odds_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE polymarket_odds(id INTEGER PRIMARY KEY, fixture_id TEXT, source TEXT,"
        "home_prob REAL, away_prob REAL, fetched_at TEXT)"
    )
    conn.execute(
        "INSERT INTO polymarket_odds(fixture_id,source,home_prob,away_prob,fetched_at) "
        "VALUES('m1','polymarket',0.585,0.165,'2026-06-19T00:00:00')"
    )
    conn.commit()
    return conn


def test_odds_source_returns_both_sides():
    conn = _odds_conn()
    pred = _prediction_with_ts()
    markets = SqliteOddsSource("t", connection=conn)(pred)
    by_outcome = {m.model_outcome: m for m in markets}
    assert set(by_outcome) == {"HOME_WIN", "AWAY_WIN"}
    assert by_outcome["HOME_WIN"].market_probability == Decimal("0.585")
    assert by_outcome["AWAY_WIN"].market_probability == Decimal("0.165")
    assert by_outcome["HOME_WIN"].condition_id == "m1:HOME_WIN"


def test_odds_source_empty_when_no_row():
    conn = _odds_conn()
    pred = _prediction_with_ts().model_copy(update={"event_id": "zzz"})
    assert SqliteOddsSource("t", connection=conn)(pred) == []


def test_odds_source_missing_table_is_graceful():
    conn = sqlite3.connect(":memory:")  # sin tabla polymarket_odds
    assert SqliteOddsSource("t", connection=conn)(_prediction_with_ts()) == []
