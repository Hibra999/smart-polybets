import pytest

import core.preconditions as pc
from core.schemas.precondition import PreconditionResult


def _viol(tid="wc"):
    return PreconditionResult(name="fixtures_finalized", ok=False, severity="mandatory",
                              tournament_id=tid, detail="1 sin finalizar",
                              remedy_cmd="python scripts/update_results.py --tournament wc --apply")


def test_read_warns_and_proceeds(monkeypatch, capsys):
    monkeypatch.setattr(pc, "evaluate", lambda *a, **k: [_viol()])
    pc.enforce("READ")                      # no levanta
    assert "sin finalizar" in capsys.readouterr().out


def test_money_blocks_without_force(monkeypatch):
    monkeypatch.setattr(pc, "evaluate", lambda *a, **k: [_viol()])
    with pytest.raises(SystemExit):
        pc.enforce("MONEY")


def test_money_force_needs_reason(monkeypatch):
    monkeypatch.setattr(pc, "evaluate", lambda *a, **k: [_viol()])
    with pytest.raises(SystemExit):
        pc.enforce("MONEY", force=True)     # sin reason


def test_money_force_with_reason_proceeds(monkeypatch, capsys):
    monkeypatch.setattr(pc, "evaluate", lambda *a, **k: [_viol()])
    pc.enforce("MONEY", force=True, reason="verificado a mano")
    assert "FORZADO" in capsys.readouterr().out


def test_evaluate_includes_gates_only_when_live(monkeypatch):
    monkeypatch.setattr(pc, "check_fixtures_finalized", lambda tid, **k:
                        PreconditionResult(name="fixtures_finalized", ok=True, severity="mandatory"))
    monkeypatch.setattr(pc, "check_placeholders_synced", lambda tid, **k:
                        PreconditionResult(name="placeholders_synced", ok=True, severity="advisory"))
    names_dry = [r.name for r in pc.evaluate("MONEY", tournaments=["wc"], live=False)]
    names_live = [r.name for r in pc.evaluate("MONEY", tournaments=["wc"], live=True)]
    assert "live_gates_ready" not in names_dry
    assert "live_gates_ready" in names_live
