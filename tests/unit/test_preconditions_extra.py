import sqlite3
from datetime import datetime, timedelta, timezone

import core.preconditions as pc


def _mk_db(path, fixtures, teams):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE team (id TEXT PRIMARY KEY, name TEXT, elo_rating REAL)")
    con.execute("CREATE TABLE fixture (id TEXT, home_team_id TEXT, away_team_id TEXT, "
                "kickoff_utc TEXT, status TEXT)")
    con.executemany("INSERT INTO team VALUES (?,?,?)", teams)
    con.executemany("INSERT INTO fixture VALUES (?,?,?,?,?)", fixtures)
    con.commit(); con.close()


def test_placeholder_upcoming_is_advisory_violation(tmp_path, monkeypatch):
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    soon = (now + timedelta(days=1)).isoformat()
    db = tmp_path / "t.sqlite"
    _mk_db(db, [("f1", "real", "ph", soon, "scheduled")],
           [("real", "Real", 1500.0), ("ph", "Placeholder", None)])
    monkeypatch.setattr(pc, "db_path", lambda tid: db)
    r = pc.check_placeholders_synced("liga_mx_2026", now=now)
    assert r.severity == "advisory" and r.ok is False and r.is_violation is False


def test_no_placeholders_ok(tmp_path, monkeypatch):
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    soon = (now + timedelta(days=1)).isoformat()
    db = tmp_path / "t.sqlite"
    _mk_db(db, [("f1", "a", "b", soon, "scheduled")],
           [("a", "A", 1500.0), ("b", "B", 1500.0)])
    monkeypatch.setattr(pc, "db_path", lambda tid: db)
    assert pc.check_placeholders_synced("x", now=now).ok is True


def test_live_gates(monkeypatch):
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("POLYMARKET_LIVE", "0")
    monkeypatch.delenv("POLYMARKET_KILL_SWITCH", raising=False)
    assert pc.check_live_gates_ready().is_violation is True
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0x" + "a" * 64)
    monkeypatch.setenv("POLYMARKET_LIVE", "1")
    assert pc.check_live_gates_ready().ok is True


def test_live_gate_rejects_relayer_key_as_signer(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "01967c03-b8c8-7000-8f68-8b8eaec6fd3d")
    monkeypatch.setenv("POLYMARKET_LIVE", "1")
    monkeypatch.setenv("POLYMARKET_KILL_SWITCH", "0")

    result = pc.check_live_gates_ready()

    assert result.ok is False
    assert "no es una clave EVM válida" in result.detail
