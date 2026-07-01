"""Carga de modelo Elo para fútbol y cálculo de probabilidades 1X2.

`elo_win_probabilities` es una función PURA y testeable. `FootballEloAdapter`
la usa para producir un MatchPrediction leyendo el Elo de los equipos del SQLite.

NOTA: este es el modelo Elo base. Bayes/TrueSkill (bayes_loader, trueskill_loader)
están preparados para wirearse al repo de modelos `pypro_worldcup_betting` cuando
se integre; mientras tanto el ensemble degrada a Elo.
"""
from __future__ import annotations

import math
from decimal import Decimal

from adapters.base import SportAdapter
from adapters.football.db_reader import FootballDBReader
from core.types import ModelConfidence
from core.utils import to_utc, utcnow

# Outcomes canónicos del mercado match_winner en fútbol.
HOME_WIN = "HOME_WIN"
DRAW = "DRAW"
AWAY_WIN = "AWAY_WIN"

DEFAULT_HOME_ADVANTAGE = 65.0  # puntos Elo (0 si neutral_venue)
DEFAULT_DRAW_BASE = 0.28       # probabilidad de empate cuando los equipos son parejos


def elo_win_probabilities(
    elo_home: float,
    elo_away: float,
    *,
    home_advantage: float = DEFAULT_HOME_ADVANTAGE,
    draw_base: float = DEFAULT_DRAW_BASE,
) -> dict[str, Decimal]:
    """Probabilidades {HOME_WIN, DRAW, AWAY_WIN} a partir de ratings Elo.

    Modelo: la expectativa Elo da P(home gana | no empate). El empate se modela
    como `draw_base` atenuado por cuán parejo es el partido (más parejo → más
    empate). Las tres probabilidades suman 1.
    """
    diff = (elo_home + home_advantage) - elo_away
    # Expectativa Elo estándar: prob de que home supere a away.
    exp_home = 1.0 / (1.0 + math.pow(10, -diff / 400.0))

    # El empate es máximo cuando exp_home ≈ 0.5 y decae hacia los extremos.
    draw = draw_base * (1.0 - abs(2.0 * exp_home - 1.0))
    draw = max(0.0, min(0.95, draw))

    home = exp_home * (1.0 - draw)
    away = (1.0 - exp_home) * (1.0 - draw)

    # Normalización defensiva.
    total = home + draw + away
    home, draw, away = home / total, draw / total, away / total

    q = lambda x: Decimal(str(round(x, 6)))  # noqa: E731
    return {HOME_WIN: q(home), DRAW: q(draw), AWAY_WIN: q(away)}


class FootballEloAdapter(SportAdapter):
    """Adapter de predicción basado en Elo para un torneo de fútbol."""

    sport = "football"

    def __init__(self, tournament_id: str, *, reader: FootballDBReader | None = None,
                 model_version: str = "elo-v1") -> None:
        self.tournament_id = tournament_id
        self.reader = reader or FootballDBReader(tournament_id)
        self.model_version = model_version

    def get_event_prediction(self, event_id: str):
        from research.schemas.match_prediction import MatchPrediction  # evita ciclo

        fixture = self.reader.get_fixture(event_id)
        if fixture is None:
            return None  # no inventar probabilidad si no hay evento

        home = self.reader.get_team(fixture["home_team_id"]) or {}
        away = self.reader.get_team(fixture["away_team_id"]) or {}
        elo_home = home.get("elo_rating")
        elo_away = away.get("elo_rating")
        if elo_home is None or elo_away is None:
            return None  # sin Elo no hay predicción

        home_adv = 0.0 if fixture.get("neutral_venue") else DEFAULT_HOME_ADVANTAGE
        probs = elo_win_probabilities(float(elo_home), float(elo_away), home_advantage=home_adv)

        # Confianza por tamaño de historia Elo disponible.
        sample = len(self.reader.get_elo_history(fixture["home_team_id"]))
        if sample >= 20:
            confidence = ModelConfidence.HIGH
        elif sample >= 8:
            confidence = ModelConfidence.MEDIUM
        else:
            confidence = ModelConfidence.LOW

        phase_name = fixture.get("phase_name") or "group"
        kickoff = fixture["kickoff_utc"]
        from datetime import datetime

        if isinstance(kickoff, str):
            kickoff = datetime.fromisoformat(kickoff)
        kickoff = to_utc(kickoff)

        return MatchPrediction(
            event_id=event_id,
            tournament_id=self.tournament_id,
            sport=self.sport,
            market_type="match_winner",
            participant_home=fixture.get("home_team_name") or fixture["home_team_id"],
            participant_away=fixture.get("away_team_name") or fixture["away_team_id"],
            event_start_utc=kickoff,
            event_phase="knockout" if fixture.get("phase_is_knockout") else phase_name,
            probabilities=probs,
            model_version=self.model_version,
            model_confidence=confidence,
            sample_size=sample,
            generated_at=utcnow(),
        )
