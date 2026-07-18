from core.strategy_evolution import read_strategy_header, latest_formal_version
from core.schemas.strategy_evolution import StrategyEvolutionCheck


def test_read_header():
    md = "# S\n\n## HEADER\nversion: 0.2\nstatus: draft  # comentario\nauthor: X\n"
    assert read_strategy_header(md) == ("0.2", "draft")


def test_read_header_missing():
    assert read_strategy_header("# S\nsin header\n") == (None, None)


def test_latest_formal_picks_max_date():
    evo = (
        "# EVOLUTION\n\n"
        "### 2026-07-14 · v0.1 (génesis) · [FORMAL]\n- x\n\n"
        "### 2026-07-18 · v0.1→v0.2 · [FORMAL]\n- y\n\n"
        "### 2026-07-16 · [OBSERVACIÓN]\n- z\n"
    )
    assert latest_formal_version(evo) == "0.2"


def test_latest_formal_none_when_no_formal():
    assert latest_formal_version("### 2026-07-18 · [OBSERVACIÓN]\n- z\n") is None


def test_check_schema_frozen():
    import pytest
    c = StrategyEvolutionCheck(strategy_id="s", ok=True)
    with pytest.raises(Exception):
        c.ok = False
