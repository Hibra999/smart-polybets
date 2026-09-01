"""Pipeline ensemble NFL: Elo + Bayes + TrueSkill.

Reúne los tres modelos para producir, por juego, la probabilidad de victoria del
local según cada uno. Reutiliza las piezas puras ya portadas:
  - Elo (con ventaja de localía + multiplicador de margen)
  - Bayes Beta-Bernoulli (fuerza latente → prob head-to-head)
  - TrueSkill 1v1 (draw_probability=0 para NFL)

Cada modelo emite una probabilidad para poder combinar señales y medir edge.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from adapters.football.strength_models import (
    BayesianLeague,
    expected_score,
    margin_multiplier,
    match_scores,
)
from adapters.football.trueskill import TrueSkillSystem

DEFAULT_ELO = 1500.0


@dataclass
class NFLEnsemblePipeline:
    k: float = 20.0            # K de Elo para NFL (estándar ~20)
    home_adv: float = 40.0     # ventaja de localía en puntos Elo (~2 pts)
    use_margin: bool = True
    elo: dict[str, float] = field(default_factory=dict)
    bayes: BayesianLeague = field(default_factory=BayesianLeague)
    trueskill: TrueSkillSystem = field(default_factory=lambda: TrueSkillSystem(draw_probability=0.0))
    appearances: dict[str, int] = field(default_factory=dict)

    def _elo(self, t: str) -> float:
        return self.elo.get(t, DEFAULT_ELO)

    def process_match(self, home: str, away: str, hs: int, as_: int) -> None:
        # Elo con ventaja de localía (en predicción y actualización, estilo 538).
        rh, ra = self._elo(home), self._elo(away)
        eh = expected_score(rh + self.home_adv, ra)
        sh, sa = match_scores(hs, as_)
        k = self.k * (margin_multiplier(hs, as_, rh, ra) if self.use_margin else 1.0)
        self.elo[home] = rh + k * (sh - eh)
        self.elo[away] = ra + k * (sa - (1.0 - eh))
        # Bayes + TrueSkill
        self.bayes.update_match(home, away, hs, as_)
        self.trueskill.update_match(home, away, hs, as_)
        self.appearances[home] = self.appearances.get(home, 0) + 1
        self.appearances[away] = self.appearances.get(away, 0) + 1

    def process_all(self, games: list[tuple[str, str, int, int]]) -> None:
        for home, away, hs, as_ in games:
            self.process_match(home, away, hs, as_)

    def prematch(self, home: str, away: str) -> dict:
        """Prob de que gane el LOCAL según cada modelo, sin mutar."""
        p_elo = expected_score(self._elo(home) + self.home_adv, self._elo(away))
        bh, ba = self.bayes.get(home).mean, self.bayes.get(away).mean
        p_bayes = bh / (bh + ba) if (bh + ba) > 0 else 0.5   # head-to-head Bradley-Terry-ish
        p_ts = self.trueskill.win_probability(home, away)
        return {
            "elo": p_elo, "bayes": p_bayes, "trueskill": p_ts,
            "home_match_no": self.appearances.get(home, 0) + 1,
            "away_match_no": self.appearances.get(away, 0) + 1,
        }
