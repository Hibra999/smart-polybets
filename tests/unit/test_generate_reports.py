from pathlib import Path

import pytest

from scripts.generate_reports import _report_location


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
