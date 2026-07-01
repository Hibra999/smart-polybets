"""Modelos de fuerza para fútbol — portados de pypro_worldcup_betting.

Migración fiel de los modelos Elo y Bayes (Beta-Bernoulli) del repo de modelos.
Son funciones/dataclasses PURAS (sin DB, sin Streamlit), aptas para vivir en la
capa de adapters del framework agéntico.

Equivalencias con el origen:
  - `expected_score`, `match_scores`, `margin_multiplier`, `EloSystem`  ← app/src/elo.py
  - `elo_to_prior`, `BetaBelief`, `BayesianLeague`                       ← app/src/bayes.py
  - `fifa_to_elo`                                                        ← app/src/fifa_seed.py

TrueSkill (3er modelo del origen) NO se porta: requiere la librería `trueskill`.
El criterio 'trueskill' de la estrategia degrada a Elo (mismo fallback que el
`pick_side` original). El edge activo migrado usa 'blend' (Elo+Bayes), así que no
depende de TrueSkill.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# ── Elo ──────────────────────────────────────────────────────────────────────


def expected_score(rating_a: float, rating_b: float) -> float:
    """Probabilidad logística de que A 'gane' (la E de Elo)."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def match_scores(goals_a: int, goals_b: int) -> tuple[float, float]:
    """Marcador → scores Elo (empate = 0.5)."""
    if goals_a > goals_b:
        return 1.0, 0.0
    if goals_a < goals_b:
        return 0.0, 1.0
    return 0.5, 0.5


def margin_multiplier(goals_a: int, goals_b: int, rating_a: float, rating_b: float) -> float:
    """Multiplicador por margen de victoria (estilo FiveThirtyEight). Empate = 1."""
    diff = abs(goals_a - goals_b)
    if diff == 0:
        return 1.0
    elo_diff = abs(rating_a - rating_b)
    return math.log(diff + 1.0) * (2.2 / ((elo_diff * 0.001) + 2.2))


@dataclass
class EloSystem:
    k: float = 40.0  # K alto: el Mundial son pocos partidos
    use_margin: bool = True
    ratings: dict[str, float] = field(default_factory=dict)

    def seed(self, initial: dict[str, float]) -> None:
        self.ratings = dict(initial)

    def get(self, team: str) -> float:
        return self.ratings.get(team, 1500.0)

    def update_match(self, team_a: str, team_b: str, goals_a: int, goals_b: int) -> None:
        ra, rb = self.get(team_a), self.get(team_b)
        ea = expected_score(ra, rb)
        eb = 1.0 - ea
        sa, sb = match_scores(goals_a, goals_b)
        k_eff = self.k
        if self.use_margin:
            k_eff *= margin_multiplier(goals_a, goals_b, ra, rb)
        self.ratings[team_a] = ra + k_eff * (sa - ea)
        self.ratings[team_b] = rb + k_eff * (sb - eb)


# ── Bayes (Beta-Bernoulli) ───────────────────────────────────────────────────


def elo_to_prior(elo: float, strength: float = 4.0, mean_elo: float = 1500.0) -> tuple[float, float]:
    """Elo → parámetros (a, b) de un prior Beta. `strength` = tamaño de muestra del prior."""
    p = 1.0 / (1.0 + 10 ** ((mean_elo - elo) / 400.0))
    p = min(max(p, 0.05), 0.95)
    return p * strength, (1.0 - p) * strength


@dataclass
class BetaBelief:
    alpha: float
    beta: float

    def update(self, success: float) -> None:
        """success en {1.0 (gana), 0.5 (empate), 0.0 (pierde)}."""
        self.alpha += success
        self.beta += (1.0 - success)

    @property
    def mean(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def var(self) -> float:
        a, b = self.alpha, self.beta
        return (a * b) / ((a + b) ** 2 * (a + b + 1))

    def credible_interval(self, mass: float = 0.95) -> tuple[float, float]:
        from statistics import NormalDist

        m, sd = self.mean, math.sqrt(self.var)
        z = NormalDist().inv_cdf(1 - (1 - mass) / 2)
        return max(0.0, m - z * sd), min(1.0, m + z * sd)


@dataclass
class BayesianLeague:
    beliefs: dict[str, BetaBelief] = field(default_factory=dict)

    def seed_from_elo(self, elo_ratings: dict[str, float], strength: float = 4.0) -> None:
        self.beliefs = {team: BetaBelief(*elo_to_prior(elo, strength))
                        for team, elo in elo_ratings.items()}

    def get(self, team: str) -> BetaBelief:
        if team not in self.beliefs:
            self.beliefs[team] = BetaBelief(2.0, 2.0)
        return self.beliefs[team]

    def update_match(self, team_a: str, team_b: str, goals_a: int, goals_b: int) -> None:
        if goals_a > goals_b:
            sa, sb = 1.0, 0.0
        elif goals_a < goals_b:
            sa, sb = 0.0, 1.0
        else:
            sa, sb = 0.5, 0.5
        self.get(team_a).update(sa)
        self.get(team_b).update(sb)


# ── Semilla FIFA → Elo ───────────────────────────────────────────────────────


def fifa_to_elo(fifa_points: dict[str, float], anchor_mean: float = 1500.0,
                scale: float = 0.9) -> dict[str, float]:
    """Re-centra puntos FIFA a la escala Elo clásica (~1500 media)."""
    if not fifa_points:
        return {}
    mean_pts = sum(fifa_points.values()) / len(fifa_points)
    return {team: anchor_mean + (pts - mean_pts) * scale for team, pts in fifa_points.items()}
