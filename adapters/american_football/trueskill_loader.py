"""FootballAmericano TrueSkill adapter — migrado de sports_bet (NFL).

Corre el pipeline TrueSkill sobre los juegos YA JUGADOS (leídos del SQLite NFL) y
emite un MatchPrediction binario (HOME_WIN / AWAY_WIN) con la probabilidad de
victoria TrueSkill. La estrategia NFL usa `side_criterion=trueskill`.

Mercado binario sin empate (los empates NFL son <0.5%).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from adapters.american_football.db_reader import AmericanFootballDBReader
from adapters.american_football.nfl_pipeline import NFLPipeline
from adapters.base import SportAdapter
from core.types import ModelConfidence
from core.utils import to_utc, utcnow

HOME_WIN = "HOME_WIN"
AWAY_WIN = "AWAY_WIN"


def _q(x: float) -> Decimal:
    return Decimal(str(round(float(x), 6)))


class AmericanFootballTrueSkillAdapter(SportAdapter):
    """Predicción TrueSkill para una temporada NFL."""

    sport = "american_football"

    def __init__(self, tournament_id: str, *, reader: AmericanFootballDBReader | None = None,
                 model_version: str = "nfl-trueskill-v1") -> None:
        self.tournament_id = tournament_id
        self.reader = reader or AmericanFootballDBReader(tournament_id)
        self.model_version = model_version

    def _run_pipeline(self, before_utc: str) -> NFLPipeline:
        pipe = NFLPipeline()
        for fx in self.reader.get_finished_fixtures(before_utc=before_utc):
            pipe.process_match(
                fx["home_team_id"], fx["away_team_id"],
                int(fx["home_score"]), int(fx["away_score"]),
            )
        return pipe

    def get_event_prediction(self, event_id: str):
        from research.schemas.match_prediction import MatchPrediction

        game = self.reader.get_game(event_id)
        if game is None:
            return None
        home_id, away_id = game["home_team_id"], game["away_team_id"]

        kickoff_raw = game["kickoff_utc"]
        kickoff = (
            datetime.fromisoformat(kickoff_raw) if isinstance(kickoff_raw, str) else kickoff_raw
        )
        kickoff = to_utc(kickoff)
        before = kickoff_raw if isinstance(kickoff_raw, str) else kickoff.isoformat()

        pipe = self._run_pipeline(before_utc=before)
        snap = pipe.prematch(home_id, away_id)

        ts = {HOME_WIN: _q(snap["ts_home"]), AWAY_WIN: _q(snap["ts_away"])}

        played = min(snap["home_match_no"] - 1, snap["away_match_no"] - 1)
        if played >= 8:
            confidence = ModelConfidence.HIGH
        elif played >= 3:
            confidence = ModelConfidence.MEDIUM
        else:
            confidence = ModelConfidence.LOW

        phase = (game.get("week_phase") or "regular").lower()
        return MatchPrediction(
            event_id=event_id,
            tournament_id=self.tournament_id,
            sport=self.sport,
            market_type="game_winner",
            participant_home=game.get("home_team_name") or home_id,
            participant_away=game.get("away_team_name") or away_id,
            event_start_utc=kickoff,
            event_phase="playoff" if phase != "regular" else "regular_season",
            probabilities=dict(ts),                       # canónico = TrueSkill
            components={"trueskill": ts},
            appearances={HOME_WIN: snap["home_match_no"], AWAY_WIN: snap["away_match_no"]},
            model_version=self.model_version,
            model_confidence=confidence,
            sample_size=played,
            generated_at=utcnow(),
        )
