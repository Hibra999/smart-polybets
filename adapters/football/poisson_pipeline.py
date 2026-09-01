"""Carga datos y ajusta el modelo Poisson de goles de una liga.

Combina ``historical_match`` y fixtures finalizados del SQLite del torneo.

y ajusta `PoissonGoalsModel`. Es un pipeline aparte: no interfiere con
FootballModelPipeline (Elo/Bayes/TrueSkill). Sólo lee la DB (read-only) vía el reader.
"""
from __future__ import annotations

from adapters.football.db_reader import FootballDBReader
from adapters.football.poisson import GoalsForecast, PoissonGoalsModel


def load_goal_matches(tournament_id: str) -> list[tuple[str, str, int, int]]:
    """Todos los partidos reales con goles: histórico + finished del torneo."""
    reader = FootballDBReader(tournament_id)
    matches: list[tuple[str, str, int, int]] = []

    # 1) histórico estático (puede no existir si no se corrió la migración)
    if reader.query(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='historical_match'"
    ):
        hist = reader.query(
            "SELECT home_team_id, away_team_id, home_goals, away_goals "
            "FROM historical_match ORDER BY match_date"
        )
        matches += [
            (r["home_team_id"], r["away_team_id"], r["home_goals"], r["away_goals"])
            for r in hist
        ]

    # 2) partidos del torneo ya jugados
    fin = reader.query(
        "SELECT home_team_id, away_team_id, home_goals, away_goals "
        "FROM fixture WHERE status='finished' AND home_goals IS NOT NULL "
        "AND away_goals IS NOT NULL ORDER BY kickoff_utc"
    )
    matches += [
        (r["home_team_id"], r["away_team_id"], r["home_goals"], r["away_goals"])
        for r in fin
    ]
    return matches


class FootballPoissonPipeline:
    """Ajusta el modelo una vez y pronostica goles de cualquier emparejamiento."""

    def __init__(self, tournament_id: str, *,
                 shrink_k: float = 5.0, neutral: bool = False) -> None:
        self.tournament_id = tournament_id
        self.model = PoissonGoalsModel(shrink_k=shrink_k, neutral=neutral)
        self._fitted = False

    def fit(self) -> FootballPoissonPipeline:
        self.model.fit(load_goal_matches(self.tournament_id))
        self._fitted = True
        return self

    def forecast(self, home: str, away: str) -> GoalsForecast:
        if not self._fitted:
            self.fit()
        return self.model.forecast(home, away)
