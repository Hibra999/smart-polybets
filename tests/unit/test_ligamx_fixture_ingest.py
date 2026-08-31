from datetime import UTC, datetime
from types import SimpleNamespace

from data.liga_mx_2026.ingest import fetch_fixtures_pm as ingest
from venue.matching import canon


def _match(home: str, away: str, kickoff: datetime):
    return SimpleNamespace(
        home_disp=home,
        away_disp=away,
        home_canon=canon(home),
        away_canon=canon(away),
        kickoff=kickoff,
        has_winner_market=True,
    )


def test_include_closed_filters_apertura_and_deduplicates(monkeypatch):
    calls = []

    def fake_match_events(*, tag_id, closed):
        calls.append((tag_id, closed))
        if closed:
            return [
                _match("América", "Guadalajara", datetime(2026, 8, 1, 1, tzinfo=UTC)),
                _match("Cruz Azul", "Pumas UNAM", datetime(2026, 7, 15, tzinfo=UTC)),
            ]
        return [
            _match("América", "Guadalajara", datetime(2026, 8, 1, 2, tzinfo=UTC)),
            _match("Toluca", "Monterrey", datetime(2026, 12, 14, tzinfo=UTC)),
        ]

    monkeypatch.setattr(ingest, "match_events", fake_match_events)

    assert ingest.discover_matches(include_closed=True) == [
        ("america", "guadalajara", "2026-08-01T02:00:00+00:00")
    ]
    assert calls == [(102448, True), (102448, False)]
