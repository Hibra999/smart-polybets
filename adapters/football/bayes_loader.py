"""Adapter Bayesiano compatible que degrada explícitamente al modelo Elo."""
from __future__ import annotations

from adapters.base import SportAdapter
from adapters.football.db_reader import FootballDBReader
from adapters.football.elo_loader import FootballEloAdapter


class FootballBayesAdapter(SportAdapter):
    sport = "football"

    def __init__(self, tournament_id: str, *, reader: FootballDBReader | None = None) -> None:
        self.tournament_id = tournament_id
        self.reader = reader or FootballDBReader(tournament_id)
        self._fallback = FootballEloAdapter(
            tournament_id, reader=self.reader, model_version="bayes-v1-elofallback"
        )

    def get_event_prediction(self, event_id: str):
        return self._fallback.get_event_prediction(event_id)
