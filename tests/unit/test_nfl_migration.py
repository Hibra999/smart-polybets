"""Tests de la migración NFL (sports_bet): pipeline TrueSkill, adapter, estrategia."""
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from adapters.american_football.db_reader import AmericanFootballDBReader
from adapters.american_football.nfl_pipeline import NFLPipeline
from adapters.american_football.trueskill_loader import AmericanFootballTrueSkillAdapter
from research.functions.strategy_selection import pick_side
from tournaments.registry import load_active_strategy

DDL = (Path(__file__).resolve().parents[2] / "data" / "_schema" / "american_football.sql"
       ).read_text(encoding="utf-8")


def _seed() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(DDL)
    conn.execute("INSERT INTO tournament(id,name,sport,season_year) "
                 "VALUES('nfl_2026','NFL','american_football',2026)")
    for code, name in [("KC", "Chiefs"), ("SF", "49ers"), ("DEN", "Broncos"), ("SEA", "Seahawks")]:
        conn.execute("INSERT INTO team(id,tournament_id,name) VALUES(?,?,?)", (code, "nfl_2026", name))
    conn.execute("INSERT INTO week(id,tournament_id,week_number,phase) VALUES('w1','nfl_2026',1,'regular')")
    conn.execute("INSERT INTO week(id,tournament_id,week_number,phase) VALUES('w2','nfl_2026',2,'regular')")
    # week 1 jugada: KC gana (sube rating), SF PIERDE vs SEA (baja rating).
    # TrueSkill ignora el margen: lo que importa es ganar/perder, no el marcador.
    conn.execute("INSERT INTO fixture(id,tournament_id,week_id,home_team_id,away_team_id,"
                 "kickoff_utc,status,home_score,away_score,winner_team_id) "
                 "VALUES('g1','nfl_2026','w1','KC','DEN','2026-09-07T17:00:00+00:00','finished',31,10,'KC')")
    conn.execute("INSERT INTO fixture(id,tournament_id,week_id,home_team_id,away_team_id,"
                 "kickoff_utc,status,home_score,away_score,winner_team_id) "
                 "VALUES('g2','nfl_2026','w1','SF','SEA','2026-09-07T17:00:00+00:00','finished',17,24,'SEA')")
    # week 2 programado: KC vs SF
    conn.execute("INSERT INTO fixture(id,tournament_id,week_id,home_team_id,away_team_id,"
                 "kickoff_utc,status) VALUES('g3','nfl_2026','w2','KC','SF','2026-09-14T17:00:00+00:00','scheduled')")
    conn.commit()
    return conn


def test_nfl_pipeline_winprob():
    pipe = NFLPipeline()
    pipe.process_all([("KC", "DEN", 31, 10), ("KC", "SEA", 28, 14)])  # KC gana 2
    snap = pipe.prematch("KC", "DEN")
    assert snap["p_home"] > 0.5            # KC (ganó) favorito sobre DEN (perdió)
    assert snap["home_match_no"] == 3      # KC jugó 2 → próxima es la 3ª


def test_nfl_pipeline_symmetric_fresh():
    pipe = NFLPipeline()
    # sin juegos: dos equipos fresh → 50/50
    assert abs(pipe.prematch("A", "B")["p_home"] - 0.5) < 1e-9


def test_nfl_adapter_prediction():
    conn = _seed()
    reader = AmericanFootballDBReader("nfl_2026", connection=conn)
    pred = AmericanFootballTrueSkillAdapter("nfl_2026", reader=reader).get_event_prediction("g3")
    assert pred is not None
    assert pred.market_type == "game_winner"
    assert set(pred.components["trueskill"]) == {"HOME_WIN", "AWAY_WIN"}
    # KC goleó (31-10) → mejor rating que SF (24-20) → favorito
    assert pred.components["trueskill"]["HOME_WIN"] > Decimal("0.5")
    assert pred.participant_home == "Chiefs"


def test_nfl_adapter_missing_game():
    conn = _seed()
    reader = AmericanFootballDBReader("nfl_2026", connection=conn)
    assert AmericanFootballTrueSkillAdapter("nfl_2026", reader=reader).get_event_prediction("zzz") is None


def test_nfl_pick_side_trueskill():
    conn = _seed()
    reader = AmericanFootballDBReader("nfl_2026", connection=conn)
    pred = AmericanFootballTrueSkillAdapter("nfl_2026", reader=reader).get_event_prediction("g3")
    pk = pick_side(pred, "trueskill", Decimal("0.5"))
    assert pk["side"] == "HOME_WIN"        # KC
    assert pk["model_prob"] == pred.components["trueskill"]["HOME_WIN"]


def test_nfl_active_strategy_is_trueskill():
    s = load_active_strategy("nfl_2026")
    assert s is not None
    assert s.strategy_id == "game_winner_v1"
    assert s.side_criterion == "trueskill"
    assert s.outcomes == ["HOME_WIN", "AWAY_WIN"]
    assert s.is_approved
