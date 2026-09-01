import importlib

from core.schemas.precondition import PreconditionResult


def _load(monkeypatch, results):
    mod = importlib.import_module("scripts.check_freshness")
    monkeypatch.setattr(mod.pc, "evaluate", lambda *a, **k: results)
    return mod


def test_exit_zero_when_clean(monkeypatch, capsys):
    mod = _load(monkeypatch, [PreconditionResult(name="fixtures_finalized", ok=True,
                                                 severity="mandatory", tournament_id="liga")])
    assert mod.run(as_json=False) == 0


def test_exit_two_on_violation(monkeypatch):
    mod = _load(monkeypatch, [PreconditionResult(name="fixtures_finalized", ok=False,
                                                 severity="mandatory", tournament_id="liga",
                                                 detail="1 sin finalizar")])
    assert mod.run(as_json=False) == 2


def test_checks_every_registered_tournament(monkeypatch):
    mod = importlib.import_module("scripts.check_freshness")
    seen = []

    def evaluate(_tier, *, tournaments):
        seen.extend(tournaments)
        return []

    monkeypatch.setattr(mod.pc, "evaluate", evaluate)
    assert mod.run(as_json=False) == 0
    assert set(seen) == set(mod.TOURNAMENTS)
