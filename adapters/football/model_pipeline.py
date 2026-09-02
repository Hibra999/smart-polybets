"""Pipeline evolutivo Elo+Bayes+TrueSkill para fútbol.

Siembra Elo y Bayes desde los ratings iniciales del torneo, procesa los partidos
ya jugados en orden cronológico (Elo + Bayes en paralelo) y expone la foto
pre-partido (`prematch`) de cualquier emparejamiento con el estado ACTUAL, sin
mutar los modelos. Puro: no toca la DB.

Se siembra directamente desde ``team.elo_rating`` del SQLite del torneo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from adapters.football.elo_loader import AWAY_WIN, DRAW, HOME_WIN, elo_win_probabilities
from adapters.football.strength_models import (
    BayesianLeague,
    EloSystem,
)
from adapters.football.trueskill import TrueSkillSystem


@dataclass
class FootballModelPipeline:
    elo: EloSystem = field(default_factory=lambda: EloSystem(k=40.0))
    bayes: BayesianLeague = field(default_factory=BayesianLeague)
    trueskill: TrueSkillSystem = field(default_factory=TrueSkillSystem)
    appearances: dict[str, int] = field(default_factory=dict)
    # Ventaja de localía en puntos Elo. Se aplica
    # al Elo (expectativa y updates); Bayes/TrueSkill quedan sin localía (son
    # señales de fuerza relativa, no de precio — documentado en TOURNAMENT.md).
    home_adv_elo: float = 0.0

    def __post_init__(self) -> None:
        self.elo.home_adv = self.home_adv_elo

    def seed(self, initial_elo: dict[str, float], *, bayes_strength: float = 4.0) -> None:
        self.elo.seed(initial_elo)
        self.bayes.seed_from_elo(initial_elo, strength=bayes_strength)
        self.trueskill.seed_from_elo(initial_elo)

    def process_match(self, home: str, away: str, hg: int, ag: int) -> None:
        """Actualiza Elo+Bayes+TrueSkill con un partido jugado y suma aparición."""
        self.appearances[home] = self.appearances.get(home, 0) + 1
        self.appearances[away] = self.appearances.get(away, 0) + 1
        self.elo.update_match(home, away, hg, ag)
        self.bayes.update_match(home, away, hg, ag)
        self.trueskill.update_match(home, away, hg, ag)

    def process_all(self, matches: list[tuple[str, str, int, int]]) -> None:
        """matches: lista de (home, away, home_goals, away_goals) ya jugados, en orden."""
        for home, away, hg, ag in matches:
            self.process_match(home, away, hg, ag)

    def prematch(self, home: str, away: str) -> dict:
        """Foto pre-partido con el estado actual (sin mutar). Mismo formato que el
        match_log del origen (sin resultado).

        - p_home/p_draw/p_away: probabilidades Elo 1X2
        - bayes_home/away: media bayesiana de la fuerza latente de cada lado
        - home/away_match_no: número de aparición que tendría cada lado (warmup)
        """
        elo = elo_win_probabilities(
            self.elo.get(home), self.elo.get(away), home_advantage=self.home_adv_elo
        )
        ts_home = self.trueskill.win_probability(home, away)
        return {
            "home": home,
            "away": away,
            "p_home": float(elo[HOME_WIN]),
            "p_draw": float(elo[DRAW]),
            "p_away": float(elo[AWAY_WIN]),
            "bayes_home": self.bayes.get(home).mean,
            "bayes_away": self.bayes.get(away).mean,
            "ts_home": ts_home,
            "ts_away": 1.0 - ts_home,
            "home_match_no": self.appearances.get(home, 0) + 1,
            "away_match_no": self.appearances.get(away, 0) + 1,
        }
