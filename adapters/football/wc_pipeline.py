"""Pipeline Elo+Bayes — portado de pypro_worldcup_betting (app/src/pipeline.py).

Siembra Elo y Bayes desde los ratings iniciales del torneo, procesa los partidos
ya jugados en orden cronológico (Elo + Bayes en paralelo) y expone la foto
pre-partido (`prematch`) de cualquier emparejamiento con el estado ACTUAL, sin
mutar los modelos. Puro: no toca la DB.

A diferencia del origen (que siembra desde puntos FIFA), aquí se siembra
directamente desde el Elo inicial del torneo (`team.elo_rating` del SQLite del
agente), que ya es el equivalente a `fifa_to_elo(fifa_points)`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from adapters.football.wc_models import (
    BayesianLeague,
    EloSystem,
)
from adapters.football.wc_trueskill import TrueSkillSystem


@dataclass
class WorldCupPipeline:
    elo: EloSystem = field(default_factory=lambda: EloSystem(k=40.0))
    bayes: BayesianLeague = field(default_factory=BayesianLeague)
    trueskill: TrueSkillSystem = field(default_factory=TrueSkillSystem)
    appearances: dict[str, int] = field(default_factory=dict)
    # Ventaja de localía en puntos Elo (0 = sede neutral, ej. Mundial). Se aplica
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

        - p_home: prob. Elo de que el local gane (la E de Elo)
        - bayes_home/away: media bayesiana de la fuerza latente de cada lado
        - home/away_match_no: número de aparición que tendría cada lado (warmup)
        """
        p_home = self.elo.expected_home(home, away)  # aplica home_adv si hay
        ts_home = self.trueskill.win_probability(home, away)
        return {
            "home": home,
            "away": away,
            "p_home": p_home,
            "p_away": 1.0 - p_home,
            "bayes_home": self.bayes.get(home).mean,
            "bayes_away": self.bayes.get(away).mean,
            "ts_home": ts_home,
            "ts_away": 1.0 - ts_home,
            "home_match_no": self.appearances.get(home, 0) + 1,
            "away_match_no": self.appearances.get(away, 0) + 1,
        }
