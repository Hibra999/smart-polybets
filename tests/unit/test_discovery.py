from datetime import datetime, timezone

from venue import discovery


class _Mkt:
    def __init__(self, q): self.question = q


class _Sched:
    def __init__(self, t): self.start_time = t


class _Ev:
    def __init__(self, title, markets, start):
        self.title = title; self.markets = markets; self.schedule = _Sched(start)


class _Page:
    def __init__(self, items): self.items = items


class _Pub:
    def list_events(self, *, tag_ids, closed, page_size):
        return [_Page([
            _Ev("Necaxa vs. Atlante", [_Mkt("Will Necaxa win on 2026-09-05?")],
                datetime(2026, 7, 2, 19, tzinfo=timezone.utc)),
            _Ev("Liga MX Champion", [_Mkt("Will Necaxa win Liga MX?")], None),
        ])]


def test_list_events_returns_raw(monkeypatch):
    monkeypatch.setattr(discovery, "build_public_client", lambda: _Pub())
    assert len(discovery.list_events(tag_id=102448)) == 2


def test_match_events_parses_and_filters(monkeypatch):
    monkeypatch.setattr(discovery, "build_public_client", lambda: _Pub())
    mes = discovery.match_events(tag_id=102448)
    assert len(mes) == 1                       # el evento de campeón (sin 'vs') se salta
    me = mes[0]
    assert me.home_canon == "necaxa" and me.away_canon == "atlante"
    assert me.has_winner_market is True
    assert me.kickoff.year == 2026
