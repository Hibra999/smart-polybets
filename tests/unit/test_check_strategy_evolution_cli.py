import importlib

from core.schemas.strategy_evolution import StrategyEvolutionCheck


def _load(monkeypatch, results):
    mod = importlib.import_module("scripts.check_strategy_evolution")
    monkeypatch.setattr(mod.se, "evaluate_all", lambda: results)
    return mod


def test_exit_zero_all_ok(monkeypatch):
    mod = _load(monkeypatch, [StrategyEvolutionCheck(strategy_id="s", ok=True)])
    assert mod.run(as_json=False) == 0


def test_exit_two_on_drift(monkeypatch):
    mod = _load(monkeypatch, [StrategyEvolutionCheck(strategy_id="s", ok=False, detail="drift")])
    assert mod.run(as_json=False) == 2
