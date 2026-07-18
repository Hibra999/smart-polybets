from pathlib import Path

import core.strategy_evolution as se


def _mk(dirp: Path, strat: str, evo: str | None):
    dirp.mkdir(parents=True, exist_ok=True)
    (dirp / "STRATEGY.md").write_text(strat, encoding="utf-8")
    if evo is not None:
        (dirp / "EVOLUTION.md").write_text(evo, encoding="utf-8")


def test_ok_when_versions_match(tmp_path):
    d = tmp_path / "s"
    _mk(d, "## HEADER\nversion: 0.2\nstatus: draft\n",
        "### 2026-07-18 · v0.1→v0.2 · [FORMAL]\n- x\n")
    r = se.check_strategy(d)
    assert r.ok is True


def test_drift_when_versions_differ(tmp_path):
    d = tmp_path / "s"
    _mk(d, "## HEADER\nversion: 0.2\nstatus: draft\n",
        "### 2026-07-14 · v0.1 (génesis) · [FORMAL]\n- x\n")
    r = se.check_strategy(d)
    assert r.ok is False and "drift" in r.detail.lower()


def test_missing_evolution(tmp_path):
    d = tmp_path / "s"
    _mk(d, "## HEADER\nversion: 0.1\nstatus: draft\n", None)
    r = se.check_strategy(d)
    assert r.ok is False and "EVOLUTION" in r.detail


def test_no_formal_entry(tmp_path):
    d = tmp_path / "s"
    _mk(d, "## HEADER\nversion: 0.1\nstatus: draft\n",
        "### 2026-07-18 · [OBSERVACIÓN]\n- z\n")
    r = se.check_strategy(d)
    assert r.ok is False and "FORMAL" in r.detail
