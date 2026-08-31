from types import SimpleNamespace

import pytest

from scripts import place_bets


def test_run_reports_empty_opportunity_as_skip(monkeypatch, capsys, tmp_path):
    reader = SimpleNamespace(query=lambda *args: [{"id": "event_1"}])
    monkeypatch.setattr(place_bets, "SQLiteReader", lambda *_: reader)
    monkeypatch.setattr(place_bets, "LocalStateClient", lambda *args, **kwargs: object())
    monkeypatch.setattr(place_bets, "PolymarketLiveSource", lambda **kwargs: object())
    monkeypatch.setattr(
        place_bets,
        "PolymarketBroker",
        lambda **kwargs: SimpleNamespace(live=False, _blocked_reason=None),
    )
    monkeypatch.setattr(place_bets.full_analysis, "run", lambda *args, **kwargs: [])

    place_bets.run("2026-09-05", 1000, False, str(tmp_path / "state.json"), "liga_mx_2026")

    output = capsys.readouterr().out
    assert "[SKIP]" in output
    assert "volumen insuficiente" in output


def test_observe_draft_rejects_live(tmp_path):
    with pytest.raises(ValueError, match="no se puede combinar"):
        place_bets.run(
            "2026-09-05", 1000, True, str(tmp_path / "state.json"),
            "liga_mx_2026", True,
        )
