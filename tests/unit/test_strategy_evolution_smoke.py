"""Smoke: las estrategias reales del repo no tienen drift (bootstrap al día)."""
from core.strategy_evolution import evaluate_all, check_strategy, strategy_dirs


def test_all_real_strategies_have_evolution_up_to_date():
    results = evaluate_all()
    assert results, "no se encontraron estrategias"
    bad = [r for r in results if not r.ok]
    assert not bad, f"estrategias con drift: {[(r.strategy_id, r.detail) for r in bad]}"


def test_doc_only_strategy_is_ok():
    # theta_lay_v1 es doc-only (no se carga con el loader) pero igual valida por EVOLUTION.md
    d = next(p for p in strategy_dirs() if p.name == "theta_lay_v1")
    assert check_strategy(d).ok is True
