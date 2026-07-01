"""Pipeline TrueSkill para NFL — migrado de sports_bet/code/analysis_true_skill.py.

El origen usa la librería `trueskill` (rate_1vs1 ganador/perdedor) y elige el equipo
de mayor rating. Acá se reutiliza el port puro 1v1 (`wc_trueskill.TrueSkillSystem`,
validado contra la lib a 1e-5) y se expone la **probabilidad de victoria** TrueSkill
para poder calcular edge vs el mercado (el origen solo comparaba μ).

Siembra FRESH (todos los equipos arrancan en N(25, 8.3)) y procesa los juegos
jugados en orden cronológico. Puro: no toca la DB.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# TrueSkill 1v1 puro (vive en adapters/football pero es un modelo genérico).
from adapters.football.wc_trueskill import TrueSkillSystem


@dataclass
class NFLPipeline:
    # NFL prácticamente no tiene empates → draw_probability bajo.
    trueskill: TrueSkillSystem = field(
        default_factory=lambda: TrueSkillSystem(draw_probability=0.0)
    )
    appearances: dict[str, int] = field(default_factory=dict)

    def process_match(self, home: str, away: str, hs: int, as_: int) -> None:
        self.appearances[home] = self.appearances.get(home, 0) + 1
        self.appearances[away] = self.appearances.get(away, 0) + 1
        self.trueskill.update_match(home, away, hs, as_)

    def process_all(self, games: list[tuple[str, str, int, int]]) -> None:
        """games: lista de (home, away, home_score, away_score) jugados, en orden."""
        for home, away, hs, as_ in games:
            self.process_match(home, away, hs, as_)

    def prematch(self, home: str, away: str) -> dict:
        """Foto pre-partido con el estado actual (sin mutar)."""
        ts_home = self.trueskill.win_probability(home, away)
        return {
            "home": home,
            "away": away,
            "p_home": ts_home,
            "p_away": 1.0 - ts_home,
            "ts_home": ts_home,
            "ts_away": 1.0 - ts_home,
            "home_match_no": self.appearances.get(home, 0) + 1,
            "away_match_no": self.appearances.get(away, 0) + 1,
        }
