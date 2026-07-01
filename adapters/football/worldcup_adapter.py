"""FootballWorldCupAdapter — adapter de modelo migrado de pypro_worldcup_betting.

Corre el pipeline Elo+Bayes sobre los partidos YA JUGADOS del torneo (leídos del
SQLite del agente) y emite un MatchPrediction para un fixture programado, con los
componentes por modelo (elo/bayes) y el número de aparición de cada lado (para la
regla de warmup `start_match_no`).

A diferencia del FootballEloAdapter simple:
  - Siembra Bayes además de Elo y evoluciona ambos con los resultados reales.
  - NO añade ventaja de localía (el modelo worldcup es de torneo neutral).
  - El mercado es binario (HOME_WIN / AWAY_WIN), como las apuestas al ganador.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from adapters.base import SportAdapter
from adapters.football.db_reader import FootballDBReader
from adapters.football.wc_pipeline import WorldCupPipeline
from core.types import ModelConfidence
from core.utils import to_utc, utcnow

HOME_WIN = "HOME_WIN"
AWAY_WIN = "AWAY_WIN"
ANCHOR_ELO = 1500.0  # Elo neutral para equipos sin semilla (el modelo los trata como media)


def _q(x: float) -> Decimal:
    return Decimal(str(round(float(x), 6)))


class FootballWorldCupAdapter(SportAdapter):
    """Predicción Elo+Bayes evolutiva para un torneo de fútbol."""

    sport = "football"

    def __init__(self, tournament_id: str, *, reader: FootballDBReader | None = None,
                 model_version: str = "wc-elo-bayes-v1", bayes_strength: float = 4.0) -> None:
        self.tournament_id = tournament_id
        self.reader = reader or FootballDBReader(tournament_id)
        self.model_version = model_version
        self.bayes_strength = bayes_strength

    def _run_pipeline(self, before_utc: str, seed: dict[str, float]) -> WorldCupPipeline:
        pipe = WorldCupPipeline()
        pipe.seed(seed, bayes_strength=self.bayes_strength)
        for fx in self.reader.get_finished_fixtures(before_utc=before_utc):
            pipe.process_match(
                fx["home_team_id"], fx["away_team_id"],
                int(fx["home_goals"]), int(fx["away_goals"]),
            )
        return pipe

    def get_event_prediction(self, event_id: str):
        from research.schemas.match_prediction import MatchPrediction

        fixture = self.reader.get_fixture(event_id)
        if fixture is None:
            return None
        home_id, away_id = fixture["home_team_id"], fixture["away_team_id"]

        # Equipos sin semilla Elo → ancla 1500 (el modelo los trata como media,
        # con confianza LOW). Igual que EloSystem.get() del repo origen.
        seed = self.reader.get_seed_elo()
        unseeded = [t for t in (home_id, away_id) if t not in seed]
        for t in unseeded:
            seed[t] = ANCHOR_ELO

        kickoff_raw = fixture["kickoff_utc"]
        kickoff = (
            datetime.fromisoformat(kickoff_raw) if isinstance(kickoff_raw, str) else kickoff_raw
        )
        kickoff = to_utc(kickoff)

        # Evoluciona los modelos sólo con partidos previos al kickoff objetivo.
        pipe = self._run_pipeline(
            before_utc=kickoff_raw if isinstance(kickoff_raw, str) else kickoff.isoformat(),
            seed=seed,
        )
        snap = pipe.prematch(home_id, away_id)

        elo = {HOME_WIN: _q(snap["p_home"]), AWAY_WIN: _q(snap["p_away"])}
        bayes = {HOME_WIN: _q(snap["bayes_home"]), AWAY_WIN: _q(snap["bayes_away"])}
        trueskill = {HOME_WIN: _q(snap["ts_home"]), AWAY_WIN: _q(snap["ts_away"])}

        played = min(snap["home_match_no"] - 1, snap["away_match_no"] - 1)
        if played >= 5:
            confidence = ModelConfidence.HIGH
        elif played >= 2:
            confidence = ModelConfidence.MEDIUM
        else:
            confidence = ModelConfidence.LOW

        return MatchPrediction(
            event_id=event_id,
            tournament_id=self.tournament_id,
            sport=self.sport,
            market_type="match_winner",
            participant_home=fixture.get("home_team_name") or home_id,
            participant_away=fixture.get("away_team_name") or away_id,
            event_start_utc=kickoff,
            event_phase="knockout" if fixture.get("phase_is_knockout")
            else (fixture.get("phase_name") or "group"),
            probabilities=dict(elo),                       # canónico = Elo
            components={"elo": elo, "bayes": bayes, "trueskill": trueskill},
            appearances={HOME_WIN: snap["home_match_no"], AWAY_WIN: snap["away_match_no"]},
            model_version=self.model_version,
            model_confidence=confidence,
            sample_size=played,
            generated_at=utcnow(),
        )
