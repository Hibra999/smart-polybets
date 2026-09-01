import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from data.nfl_2026.ingest.fetch_game_stats import aggregate_team_stats, upsert_team_stats
from data.nfl_2026.ingest.fetch_rosters import player_records, upsert_players

DDL = (Path(__file__).resolve().parents[2] / "data" / "_schema" / "american_football.sql"
       ).read_text(encoding="utf-8")


def _db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(DDL)
    connection.execute(
        "INSERT INTO tournament(id,name,sport,season_year) "
        "VALUES('nfl_2026','NFL','american_football',2026)")
    connection.executemany(
        "INSERT INTO team(id,tournament_id,name) VALUES(?,'nfl_2026',?)",
        [("KC", "Chiefs"), ("BUF", "Bills")])
    connection.execute(
        "INSERT INTO week(id,tournament_id,week_number,phase) "
        "VALUES('w1','nfl_2026',1,'regular')")
    connection.execute(
        "INSERT INTO fixture(id,tournament_id,week_id,home_team_id,away_team_id,"
        "kickoff_utc,status,home_score,away_score) VALUES"
        "('g1','nfl_2026','w1','KC','BUF','2026-09-01T00:00:00Z','finished',24,17)")
    connection.commit()
    connection.close()


def test_pbp_aggregation_and_idempotent_upsert(tmp_path):
    pbp = pd.DataFrame([
        {"game_id": "g1", "home_team": "KC", "away_team": "BUF", "posteam": "KC",
         "epa": 0.4, "success": 1, "yards_gained": 25, "pass_attempt": 1,
         "rush_attempt": 0, "pass_oe": 0.1},
        {"game_id": "g1", "home_team": "KC", "away_team": "BUF", "posteam": "KC",
         "epa": -0.2, "success": 0, "yards_gained": 3, "pass_attempt": 0,
         "rush_attempt": 1, "pass_oe": None},
        {"game_id": "g1", "home_team": "KC", "away_team": "BUF", "posteam": "BUF",
         "epa": -0.1, "success": 0, "yards_gained": 4, "pass_attempt": 1,
         "rush_attempt": 0, "pass_oe": -0.1},
        {"game_id": "g1", "home_team": "KC", "away_team": "BUF", "posteam": "BUF",
         "epa": 0.2, "success": 1, "yards_gained": 21, "pass_attempt": 0,
         "rush_attempt": 1, "pass_oe": None},
    ])
    records = aggregate_team_stats(pbp)
    kc = next(row for row in records if row["team_id"] == "KC")
    assert kc["offensive_epa_per_play"] == pytest.approx(0.1)
    assert kc["explosive_play_rate"] == 0.5
    assert kc["pass_rate"] == 0.5

    db = tmp_path / "nfl.sqlite"
    _db(db)
    assert upsert_team_stats(db, records) == 2
    assert upsert_team_stats(db, records) == 2
    connection = sqlite3.connect(db)
    assert connection.execute("SELECT count(*) FROM match_team_stat").fetchone()[0] == 2
    connection.close()


def test_roster_latest_week_depth_and_partial_injury_log(tmp_path):
    roster = pd.DataFrame([
        {"gsis_id": "p1", "team": "KC", "week": 1, "full_name": "QB One",
         "position": "QB", "jersey_number": 1, "years_exp": 2, "status": "ACT"},
        {"gsis_id": "p1", "team": "KC", "week": 2, "full_name": "QB One",
         "position": "QB", "jersey_number": 1, "years_exp": 2, "status": "RES"},
    ])
    depth = pd.DataFrame([{"gsis_id": "p1", "dt": "2026-08-31", "pos_rank": 1}])
    records = player_records(roster, depth)
    assert records[0]["depth_chart_rank"] == 1
    assert records[0]["status"] == "injured_ir"

    db = tmp_path / "nfl.sqlite"
    _db(db)
    assert upsert_players(db, records) == 1
    connection = sqlite3.connect(db)
    player = connection.execute(
        "SELECT status,depth_chart_rank FROM player WHERE id='p1'").fetchone()
    log = connection.execute(
        "SELECT status,error_msg FROM ingest_log WHERE entity_type='player/injury_report'"
    ).fetchone()
    connection.close()
    assert player == ("injured_ir", 1)
    assert log[0] == "partial" and "no publica" in log[1]
