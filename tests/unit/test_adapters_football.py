from decimal import Decimal

from adapters.football.db_reader import FootballDBReader
from adapters.football.elo_loader import FootballEloAdapter, elo_win_probabilities


def test_elo_probabilities_sum_to_one():
    probs = elo_win_probabilities(2100, 2000)
    assert abs(sum(float(p) for p in probs.values()) - 1.0) < 1e-9
    assert probs["HOME_WIN"] > probs["AWAY_WIN"]  # equipo más fuerte


def test_elo_equal_teams_symmetric():
    probs = elo_win_probabilities(2000, 2000, home_advantage=0)
    assert probs["HOME_WIN"] == probs["AWAY_WIN"]


def test_db_reader_fixture(football_conn):
    reader = FootballDBReader("liga_mx_2026", connection=football_conn)
    fx = reader.get_fixture("m1")
    assert fx is not None
    assert fx["home_team_name"] == "Club America"


def test_db_reader_upcoming(football_conn):
    reader = FootballDBReader("liga_mx_2026", connection=football_conn)
    assert [f["id"] for f in reader.get_upcoming_fixtures(24)] == ["m1"]


def test_elo_adapter_prediction(football_conn):
    reader = FootballDBReader("liga_mx_2026", connection=football_conn)
    pred = FootballEloAdapter("liga_mx_2026", reader=reader).get_event_prediction("m1")
    assert pred is not None
    assert pred.market_type == "match_winner"
    assert pred.prob_for("HOME_WIN") > Decimal("0")
    assert pred.participant_home == "Club America"


def test_elo_adapter_missing_event(football_conn):
    reader = FootballDBReader("liga_mx_2026", connection=football_conn)
    assert FootballEloAdapter("liga_mx_2026", reader=reader).get_event_prediction("zzz") is None


def test_availability_query(football_conn):
    reader = FootballDBReader("liga_mx_2026", connection=football_conn)
    assert reader.get_player_availability("AME") == []  # nadie lesionado por defecto
