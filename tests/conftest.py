"""Fixtures compartidos de tests.

Seeds una DB de fútbol in-memory desde el DDL canónico y provee factories de
schemas y un DjangoClient falso para testear workflows sin red.
"""
from __future__ import annotations

import sqlite3
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from core.utils import utcnow
from portfolio.schemas.portfolio_state import PortfolioState
from research.schemas.market_opportunity import MarketOpportunity

REPO_ROOT = Path(__file__).resolve().parent.parent
FOOTBALL_DDL = (REPO_ROOT / "data" / "_schema" / "football.sql").read_text(encoding="utf-8")


def seed_football(conn: sqlite3.Connection, *, kickoff_hours: float = 5.0,
                  injured: bool = False, elo_history: int = 0,
                  finished_warmup: bool = False) -> None:
    conn.executescript(FOOTBALL_DDL)
    conn.execute(
        "INSERT INTO tournament(id,name,sport,format,start_date) "
        "VALUES('fifa_world_cup_2026','FIFA WC 2026','football','world_cup','2026-06-11')"
    )
    for tid, name, elo in [("ARG", "Argentina", 2100), ("FRA", "France", 2000),
                           ("WK1", "Weak1", 1450), ("WK2", "Weak2", 1450)]:
        conn.execute(
            "INSERT INTO team(id,tournament_id,name,elo_rating) VALUES(?,?,?,?)",
            (tid, "fifa_world_cup_2026", name, elo),
        )
    conn.execute(
        "INSERT INTO player(id,tournament_id,team_id,name,status) VALUES"
        "('messi','fifa_world_cup_2026','ARG','Messi','available')"
    )

    if finished_warmup:
        # ARG y FRA juegan 2 partidos ganados c/u ANTES de m1: pasa warmup
        # (start_match_no=2) y la confianza sube a MEDIUM (played=2).
        base = utcnow() - timedelta(days=6)
        finished = [
            ("g1", "ARG", "WK1", 3, 0), ("g2", "FRA", "WK2", 2, 0),
            ("g3", "ARG", "WK2", 2, 1), ("g4", "FRA", "WK1", 1, 0),
        ]
        for i, (fid, h, a, hg, ag) in enumerate(finished):
            ko = (base + timedelta(hours=i)).isoformat()
            conn.execute(
                "INSERT INTO fixture(id,tournament_id,home_team_id,away_team_id,"
                "kickoff_utc,status,home_goals,away_goals,winner_team_id,neutral_venue) "
                "VALUES(?,?,?,?,?,'finished',?,?,?,1)",
                (fid, "fifa_world_cup_2026", h, a, ko, hg, ag, h),
            )

    kickoff = (utcnow() + timedelta(hours=kickoff_hours)).isoformat()
    conn.execute(
        "INSERT INTO fixture(id,tournament_id,home_team_id,away_team_id,kickoff_utc,"
        "status,neutral_venue) VALUES('m1','fifa_world_cup_2026','ARG','FRA',?, "
        "'scheduled',1)",
        (kickoff,),
    )

    # tabla auxiliar de cuotas (la crea la migración real; aquí la sembramos para
    # poder testear SqliteOddsSource). Con finished_warmup insertamos una cuota.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS polymarket_odds("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, fixture_id TEXT, source TEXT,"
        "home_team_id TEXT, away_team_id TEXT, home_decimal REAL, away_decimal REAL,"
        "draw_decimal REAL, home_prob REAL, away_prob REAL, fetched_at TEXT)"
    )
    if finished_warmup:
        conn.execute(
            "INSERT INTO polymarket_odds(fixture_id,source,home_team_id,away_team_id,"
            "home_prob,away_prob,fetched_at) VALUES('m1','polymarket','ARG','FRA',"
            "0.30,0.55,'2026-06-20T00:00:00+00:00')"
        )
    if injured:
        conn.execute(
            "INSERT INTO player_availability(player_id,tournament_id,status,reason) "
            "VALUES('messi','fifa_world_cup_2026','doubtful','knock')"
        )
    for i in range(elo_history):
        conn.execute(
            "INSERT INTO elo_rating_history(team_id,tournament_id,elo_before,elo_after,"
            "rated_at) VALUES('ARG','fifa_world_cup_2026',?,?,?)",
            (2090 + i, 2091 + i, f"2026-05-{(i % 28) + 1:02d}T00:00:00+00:00"),
        )
    conn.commit()


@pytest.fixture
def football_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    seed_football(conn)
    yield conn
    conn.close()


@pytest.fixture
def seeded_data_root(tmp_path, monkeypatch) -> Path:
    """Crea data_root temporal con la DB de fifa seeded y exporta DATA_ROOT."""
    db_dir = tmp_path / "fifa_world_cup_2026"
    db_dir.mkdir(parents=True)
    db_path = db_dir / "fifa_world_cup_2026.sqlite"
    conn = sqlite3.connect(db_path)
    # Partidos jugados → warmup OK + confianza MEDIUM (estrategia activa = worldcup).
    seed_football(conn, finished_warmup=True)
    conn.close()
    monkeypatch.setenv("DATA_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def portfolio_state() -> PortfolioState:
    return PortfolioState(
        bankroll_usdc=Decimal("1000"),
        drawdown_7d=Decimal("0"),
        open_positions=[],
        exposure_by_participant={},
        as_of=utcnow(),
    )


def make_opportunity(
    *,
    model_probability="0.60",
    market_probability="0.50",
    market_volume_usdc="6000",
    hours_to_event=5.0,
    event_phase="group",
    model_confidence="HIGH",
) -> MarketOpportunity:
    model_p = Decimal(model_probability)
    market_p = Decimal(market_probability)
    return MarketOpportunity(
        polymarket_condition_id="cond_1",
        polymarket_token_id="tok_1",
        outcome="YES",
        tournament_id="fifa_world_cup_2026",
        sport="football",
        event_id="m1",
        market_type="match_winner",
        strategy_id="match_winner_v1",
        model_probability=model_p,
        market_probability=market_p,
        edge=model_p - market_p,
        participant_home="Argentina",
        participant_away="France",
        event_start_utc=utcnow() + timedelta(hours=hours_to_event),
        hours_to_event=hours_to_event,
        event_phase=event_phase,
        market_volume_usdc=Decimal(market_volume_usdc),
        market_liquidity_usdc=Decimal("8000"),
        model_version="elo-v1",
        model_confidence=model_confidence,
        sample_size=25,
        generated_at=utcnow(),
        strategy_version="0.1",
    )


@pytest.fixture
def opportunity_factory():
    return make_opportunity


class FakeDjangoClient:
    """DjangoClient falso para workflows: idempotencia siempre nueva, saves no-op."""

    def __init__(self):
        self.saved = []
        self.executed = []

    def get_portfolio_state(self):
        return {"bankroll_usdc": "1000", "drawdown_7d": "0", "open_positions": [],
                "exposure_by_participant": {}}

    def check_idempotency(self, key):
        return None

    def save_decision(self, payload):
        self.saved.append(payload)
        return {"id": len(self.saved), "idempotency_key": payload["idempotency_key"]}

    def mark_executed(self, key, order_result):
        self.executed.append((key, order_result))
        return {"status": "executed"}

    def get_active_tournaments(self):
        return [{"tournament_id": "fifa_world_cup_2026"}]


@pytest.fixture
def fake_client() -> FakeDjangoClient:
    return FakeDjangoClient()
