"""Tests puros del seam de señales (signals package)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from research.schemas.match_prediction import MatchPrediction
from core.types import ModelConfidence
from signals.base import Signal
from signals.registry import register, get, clear
from signals.football import FootballSignalProvider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_prediction(elo_home: str = "0.65", elo_away: str = "0.35") -> MatchPrediction:
    return MatchPrediction(
        event_id="e1",
        tournament_id="liga_mx_2026",
        sport="football",
        market_type="match_winner",
        participant_home="Seattle",
        participant_away="Germany",
        event_start_utc=_utcnow(),
        event_phase="group",
        probabilities={"HOME_WIN": Decimal(elo_home), "AWAY_WIN": Decimal(elo_away)},
        components={"elo": {"HOME_WIN": Decimal(elo_home), "AWAY_WIN": Decimal(elo_away)}},
        appearances={"HOME_WIN": 1, "AWAY_WIN": 1},
        model_version="football-v1",
        model_confidence=ModelConfidence.MEDIUM,
        sample_size=10,
        generated_at=_utcnow(),
    )


class _FakeStrategy:
    side_criterion = "elo"
    blend_weight = Decimal("0.5")


# ── Registry ─────────────────────────────────────────────────────────────────


def test_registry_register_and_get():
    clear()
    provider = FootballSignalProvider("t1", _FakeStrategy(), predict=lambda *_: None)
    register(provider)
    assert get("football") is provider


def test_registry_clear():
    clear()
    provider = FootballSignalProvider("t1", _FakeStrategy(), predict=lambda *_: None)
    register(provider)
    clear()
    assert get("football") is None


def test_registry_get_unknown_returns_none():
    clear()
    assert get("cricket") is None


def test_provider_can_register_for_american_football():
    clear()
    provider = FootballSignalProvider(
        "nfl_2026", _FakeStrategy(), predict=lambda *_: None, sport="american_football"
    )
    register(provider)
    assert get("american_football") is provider


# ── FootballSignalProvider ────────────────────────────────────────────────────


def test_signal_home_favored():
    pred = _make_prediction(elo_home="0.65", elo_away="0.35")
    provider = FootballSignalProvider("t1", _FakeStrategy(), predict=lambda *_: pred)
    sig = provider.signal("Seattle", "Germany", event_id="e1")
    assert sig is not None
    assert sig.side == "HOME_WIN"
    assert sig.model_probability == Decimal("0.65")
    assert sig.model_confidence == "MEDIUM"
    assert sig.model_version == "football-v1"
    assert sig.sample_size == 10


def test_signal_away_favored():
    pred = _make_prediction(elo_home="0.30", elo_away="0.70")
    provider = FootballSignalProvider("t1", _FakeStrategy(), predict=lambda *_: pred)
    sig = provider.signal("Seattle", "Germany", event_id="e1")
    assert sig is not None
    assert sig.side == "AWAY_WIN"
    assert sig.model_probability == Decimal("0.70")


def test_signal_none_when_predictor_returns_none():
    provider = FootballSignalProvider("t1", _FakeStrategy(), predict=lambda *_: None)
    assert provider.signal("A", "B", event_id="e99") is None
