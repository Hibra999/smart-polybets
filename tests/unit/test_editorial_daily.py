"""Tests del editorial diario: cómputo, HTML, tweet y publicación Metricool."""
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from agent.tools import publish_tools
from agent.workflows import daily_suggestions
from core.types import ModelConfidence
from core.utils import utcnow
from editorial.functions import (
    build_backtest_to_date_html,
    build_daily_html,
    build_daily_tweet,
    build_next_predictions_html,
)
from research.schemas.match_prediction import MatchPrediction

SAMPLE = {
    "strategy": "match_winner_ligamx_v1", "side_criterion": "blend", "kelly_fraction": 0.25,
    "date": "2026-06-20", "source": "polymarket", "generated_at": "2026-06-20T07:00:00",
    "rows": [
        {"home": "Tigres", "away": "Monterrey", "kickoff": "2026-06-20T15:00:00+00:00",
         "phase": "Group Stage", "pick_side": "HOME_WIN", "pick_team": "Tigres",
         "confidence": "LOW", "elo": 0.70, "bayes": 0.63, "trueskill": 0.47,
         "poisson": 0.58, "poisson_draw": 0.24,
         "verdict": "REVIEW", "reason": "model_confidence LOW",
         "model_prob": 0.70, "market_prob": 0.575, "edge": 0.125, "stake": 50.0},
        {"home": "Pumas", "away": "Toluca", "kickoff": "2026-06-20T14:00:00+00:00",
         "phase": "Group Stage", "pick_side": "HOME_WIN", "pick_team": "Pumas",
         "confidence": "LOW", "elo": 0.80, "bayes": 0.34, "trueskill": 0.62,
         "verdict": "DISCARD", "reason": "edge negativo",
         "model_prob": 0.797, "market_prob": 0.865, "edge": -0.068, "stake": 0.0},
    ],
}


def test_tweet_under_limit_and_clean():
    t = build_daily_tweet(SAMPLE)
    assert len(t) <= 280
    assert "Tigres" in t            # el de mayor edge positivo
    assert "Pumas" not in t            # descartado, no entra
    assert "—" not in t and "--" not in t  # sin em-dashes (design rule)


def test_tweet_no_signals():
    empty = {**SAMPLE, "rows": [{"edge": -0.1, "verdict": "DISCARD",
                                 "pick_team": "X", "model_prob": 0.4, "market_prob": 0.5}]}
    t = build_daily_tweet(empty)
    assert "no encuentra valor" in t.lower()
    assert len(t) <= 280


def test_html_structure():
    h = build_daily_html(SAMPLE)
    assert h.startswith("<!DOCTYPE html>")
    assert "Tigres" in h and "Pumas" in h
    assert "Revisar" in h and "Descartar" in h     # labels de veredicto
    assert "#0F1117" in h                           # token del design system
    assert "Toluca" in h                           # escape de acentos OK
    assert "empate Poisson" in h and "modelos en desacuerdo" in h


def test_combined_predictions_html_keeps_both_markets():
    liga = {**SAMPLE, "tournament_id": "liga_mx_2026", "tournament_name": "Liga MX"}
    nfl = {
        **SAMPLE,
        "tournament_id": "nfl_2026",
        "tournament_name": "NFL",
        "rows": [SAMPLE["rows"][0]],
    }
    report = build_next_predictions_html([liga, nfl], as_of="2026-09-01")
    assert "Liga MX" in report and "NFL" in report
    assert "Próximos partidos" in report and "<b>3</b> partidos" in report


def test_backtest_html_shows_cutoff_targets_and_horizon():
    result = {
        "tournament_id": "liga_mx_2026",
        "strategy": "strategy",
        "season": "2025/2026",
        "latest_event_utc": "2026-05-01T12:00:00+00:00",
        "price_source": "closing odds",
        "coverage": {"games": 10, "with_price": 10},
        "decisions": {"AUTO": 3, "REVIEW": 2, "DISCARD": 5, "SKIP": 0},
        "performance": {
            "bankroll_initial": 1000.0, "bankroll_final": 980.0, "roi": -0.02,
            "win_rate": 0.5, "max_drawdown": 0.08, "bets": 2,
        },
        "targets": {"met": {"roi": False, "win_rate": True, "max_drawdown": True}},
        "bets": [],
    }
    data = {
        "as_of": "2026-09-01", "generated_at": "2026-09-01T00:00:00+00:00",
        "bankroll": 1000.0, "results": [result],
        "horizons": [{
            "tournament_id": "liga_mx_2026", "display_name": "Liga MX",
            "finished_to_date": 54, "latest_finished_utc": "2026-08-31T02:00:00+00:00",
        }],
    }
    report = build_backtest_to_date_html(data)
    assert "Backtest hasta 2026-09-01" in report
    assert "Temporada actual" in report and "54" in report
    assert "roi: Falla" in report and "win_rate: Cumple" in report


def test_metricool_payload_shape():
    p = publish_tools.build_payload("hola", "2026-06-20T12:00:00", "America/Mexico_City")
    assert p["providers"] == [{"network": "twitter"}]
    assert p["text"] == "hola"
    assert p["autoPublish"] is False
    assert p["publicationDate"]["timezone"] == "America/Mexico_City"


def test_metricool_dry_run_does_not_send():
    res = publish_tools.publish_tweet("hola", dry_run=True)
    assert res["dry_run"] is True
    assert res["payload"]["text"] == "hola"


def test_compute_returns_rows(seeded_data_root):
    # seeded_data_root tiene m1 (AME vs CAZ) + cuota polymarket para m1.
    date = (utcnow() + timedelta(hours=5)).strftime("%Y-%m-%d")
    data = daily_suggestions.compute(date, "liga_mx_2026", allow_draft=True)
    assert data["strategy"] == "match_winner_ligamx_v1"
    assert len(data["rows"]) >= 1
    row = data["rows"][0]
    assert row["home"] == "Club America"
    assert "verdict" in row and "edge" in row


def test_compute_supports_nfl_reader(monkeypatch):
    kickoff = utcnow() + timedelta(days=8)
    probabilities = {"HOME_WIN": Decimal("0.62"), "AWAY_WIN": Decimal("0.38")}
    prediction = MatchPrediction(
        event_id="nfl-game", tournament_id="nfl_2026", sport="american_football",
        market_type="game_winner", participant_home="Chiefs", participant_away="Raiders",
        event_start_utc=kickoff, event_phase="regular_season", probabilities=probabilities,
        components={"trueskill": probabilities},
        appearances={"HOME_WIN": 5, "AWAY_WIN": 5}, model_version="test",
        model_confidence=ModelConfidence.MEDIUM, sample_size=4, generated_at=utcnow(),
    )
    reader = SimpleNamespace(query=lambda *_args: [{"id": "nfl-game"}])
    monkeypatch.setattr(
        daily_suggestions, "get_adapter", lambda _tid: SimpleNamespace(reader=reader)
    )
    monkeypatch.setattr(daily_suggestions, "get_event_prediction", lambda *_args: prediction)

    data = daily_suggestions.compute(
        kickoff.strftime("%Y-%m-%d"),
        "nfl_2026",
        market_source=lambda _prediction: [],
    )
    assert data["rows"][0]["trueskill"] == 0.62
    assert data["rows"][0]["poisson"] is None
