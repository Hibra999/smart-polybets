"""Modelo Elo para NFL — mercado binario game_winner (no hay empates prácticos).

`nfl_win_probabilities` es pura y testeable. NFL no usa empate (los empates son
<0.5% históricos), así que el mercado es binario HOME_WIN / AWAY_WIN.
"""
from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal

from adapters.american_football.db_reader import AmericanFootballDBReader
from adapters.base import SportAdapter
from core.types import ModelConfidence
from core.utils import to_utc, utcnow

HOME_WIN = "HOME_WIN"
AWAY_WIN = "AWAY_WIN"

DEFAULT_HOME_ADVANTAGE = 48.0  # ~2.0 pts de spread en Elo NFL


def nfl_win_probabilities(
    elo_home: float, elo_away: float, *, home_advantage: float = DEFAULT_HOME_ADVANTAGE
) -> dict[str, Decimal]:
    """Probabilidades {HOME_WIN, AWAY_WIN} desde ratings Elo (binario)."""
    diff = (elo_home + home_advantage) - elo_away
    p_home = 1.0 / (1.0 + math.pow(10, -diff / 400.0))
    q = lambda x: Decimal(str(round(x, 6)))  # noqa: E731
    return {HOME_WIN: q(p_home), AWAY_WIN: q(1.0 - p_home)}


class AmericanFootballEloAdapter(SportAdapter):
    sport = "american_football"

    def __init__(self, tournament_id: str, *, reader: AmericanFootballDBReader | None = None,
                 model_version: str = "nfl-elo-v1") -> None:
        self.tournament_id = tournament_id
        self.reader = reader or AmericanFootballDBReader(tournament_id)
        self.model_version = model_version

    def get_event_prediction(self, event_id: str):
        from research.schemas.match_prediction import MatchPrediction

        game = self.reader.get_game(event_id)
        if game is None:
            return None
        home = self.reader.get_team(game["home_team_id"]) or {}
        away = self.reader.get_team(game["away_team_id"]) or {}
        elo_home, elo_away = home.get("elo_rating"), away.get("elo_rating")
        if elo_home is None or elo_away is None:
            return None

        home_adv = 0.0 if game.get("is_international") else DEFAULT_HOME_ADVANTAGE
        probs = nfl_win_probabilities(float(elo_home), float(elo_away), home_advantage=home_adv)

        kickoff = game["kickoff_utc"]
        if isinstance(kickoff, str):
            kickoff = datetime.fromisoformat(kickoff)
        kickoff = to_utc(kickoff)

        phase = game.get("week_phase") or "regular"
        return MatchPrediction(
            event_id=event_id,
            tournament_id=self.tournament_id,
            sport=self.sport,
            market_type="game_winner",
            participant_home=game.get("home_team_name") or game["home_team_id"],
            participant_away=game.get("away_team_name") or game["away_team_id"],
            event_start_utc=kickoff,
            event_phase="playoff" if phase != "regular" else "regular_season",
            probabilities=probs,
            model_version=self.model_version,
            model_confidence=ModelConfidence.MEDIUM,
            sample_size=len(self.reader.get_team_form(game["home_team_id"], last_n=99)),
            generated_at=utcnow(),
        )
