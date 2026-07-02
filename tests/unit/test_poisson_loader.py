from research.functions import poisson_loader


class _FakeForecast:
    def prob_result(self, max_goals=10):
        return {"home": 0.5, "draw": 0.3, "away": 0.2}


class _FakePipe:
    def __init__(self, *a, **k):
        pass

    def fit(self):
        return self

    def forecast(self, home, away):
        return _FakeForecast()


class _FakeReader:
    def __init__(self, *a, **k):
        pass

    def get_fixture(self, eid):
        return {"home_team_id": "argentina", "away_team_id": "chile"} if eid == "wc_1" else None


def test_match_result_probs_ok(monkeypatch):
    poisson_loader._CACHE.clear()
    monkeypatch.setattr(poisson_loader, "_PIPELINE_CLS", _FakePipe)
    monkeypatch.setattr(poisson_loader, "_READER_CLS", _FakeReader)
    r = poisson_loader.match_result_probs("t", "wc_1")
    assert r == {"home": 0.5, "draw": 0.3, "away": 0.2}


def test_match_result_probs_no_fixture(monkeypatch):
    poisson_loader._CACHE.clear()
    monkeypatch.setattr(poisson_loader, "_PIPELINE_CLS", _FakePipe)
    monkeypatch.setattr(poisson_loader, "_READER_CLS", _FakeReader)
    assert poisson_loader.match_result_probs("t", "nope") is None
