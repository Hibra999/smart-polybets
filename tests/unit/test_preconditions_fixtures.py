import sqlite3
from datetime import datetime, timedelta, timezone

import core.preconditions as pc


def _mk_db(path, rows):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE team (id TEXT PRIMARY KEY, name TEXT, elo_rating REAL)")
    con.execute("CREATE TABLE fixture (id TEXT, home_team_id TEXT, away_team_id TEXT, "
                "kickoff_utc TEXT, status TEXT)")
    con.execute("INSERT INTO team VALUES ('a','A',1500),('b','B',1500)")
    con.executemany("INSERT INTO fixture VALUES (?,?,?,?,?)", rows)
    con.commit(); con.close()


def test_fixtures_finalized_flags_past_scheduled(tmp_path, monkeypatch):
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    old = (now - timedelta(hours=5)).isoformat()      # jugado, sin finalizar
    con_db = tmp_path / "t.sqlite"
    _mk_db(con_db, [("f1", "a", "b", old, "scheduled")])
    monkeypatch.setattr(pc, "db_path", lambda tid: con_db)
    r = pc.check_fixtures_finalized("liga_mx_2026", now=now)
    assert r.is_violation is True
    assert "update_results.py --tournament liga_mx_2026" in r.remedy_cmd


def test_in_play_not_flagged(tmp_path, monkeypatch):
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(minutes=30)).isoformat()  # en juego ahora
    con_db = tmp_path / "t.sqlite"
    _mk_db(con_db, [("f1", "a", "b", recent, "scheduled")])
    monkeypatch.setattr(pc, "db_path", lambda tid: con_db)
    assert pc.check_fixtures_finalized("liga_mx_2026", now=now).ok is True


def test_missing_db_is_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "db_path", lambda tid: tmp_path / "nope.sqlite")
    r = pc.check_fixtures_finalized("x", now=datetime(2026, 7, 17, tzinfo=timezone.utc))
    assert r.ok is None and r.is_violation is False
