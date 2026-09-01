"""Tests del editorial diario: cómputo, HTML, tweet y publicación Metricool."""
from datetime import timedelta

from agent.tools import publish_tools
from agent.workflows import daily_suggestions
from core.utils import utcnow
from editorial.functions import build_daily_html, build_daily_tweet

SAMPLE = {
    "strategy": "match_winner_ligamx_v1", "side_criterion": "blend", "kelly_fraction": 0.25,
    "date": "2026-06-20", "source": "polymarket", "generated_at": "2026-06-20T07:00:00",
    "rows": [
        {"home": "Tigres", "away": "Monterrey", "kickoff": "2026-06-20T15:00:00+00:00",
         "phase": "Group Stage", "pick_side": "HOME_WIN", "pick_team": "Tigres",
         "confidence": "LOW", "elo": 0.70, "bayes": 0.63, "trueskill": 0.47,
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
