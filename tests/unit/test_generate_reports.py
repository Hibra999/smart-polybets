import csv
import json
from datetime import date
from pathlib import Path

import pytest

from scripts.generate_reports import _report_location, write_market_snapshots


def test_report_location_defaults_to_system_bucket():
    assert _report_location(None) == (None, "_system")


def test_report_location_accepts_editorial_subdirectory(tmp_path, monkeypatch):
    reports = tmp_path / "editorial" / "reports"
    output = reports / "_system" / "published"
    monkeypatch.setattr("scripts.generate_reports.REPORTS_ROOT", reports)

    root, bucket = _report_location(output)

    assert root == (reports / "_system").resolve()
    assert bucket == "published"


def test_report_location_rejects_docs(tmp_path, monkeypatch):
    reports = tmp_path / "editorial" / "reports"
    monkeypatch.setattr("scripts.generate_reports.REPORTS_ROOT", reports)

    with pytest.raises(ValueError, match="editorial/reports"):
        _report_location(Path(tmp_path / "docs"))


def test_market_snapshot_is_daily_idempotent_and_reconciles(monkeypatch, tmp_path):
    monkeypatch.setattr("scripts.generate_reports._settlement", lambda *_: "WON")
    prediction = {
        "tournament_id": "nfl_2026", "source": "polymarket-live",
        "generated_at": "2026-09-02T12:00:00+00:00",
        "rows": [{
            "fixture_id": "g1", "kickoff": "2026-09-03T00:00:00+00:00",
            "home": "A", "away": "B", "pick_side": "HOME_WIN",
            "token_id": "tok", "best_ask": 0.51, "top_asks": [[0.51, 100]],
            "complete_set_asks": {"HOME_WIN": 0.2, "DRAW": 0.3, "AWAY_WIN": 0.51},
            "complete_set_status": "NO_EDGE",
            "verdict": "DISCARD", "action": "NO_TRADE",
        }],
    }
    path = write_market_snapshots([prediction], tmp_path, date(2026, 9, 2))[0]
    prediction["rows"][0]["best_ask"] = 0.52
    write_market_snapshots([prediction], tmp_path, date(2026, 9, 2))

    with path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 1
    assert rows[0]["best_ask"] == "0.52"
    assert json.loads(rows[0]["ask_levels_json"]) == [[0.51, 100]]
    assert rows[0]["settlement"] == "WON"
    assert json.loads(rows[0]["complete_set_asks_json"])["DRAW"] == 0.3
    assert b"\r\n" not in path.read_bytes()
