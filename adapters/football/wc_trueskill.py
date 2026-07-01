"""TrueSkill 1v1 — port puro de pypro_worldcup_betting/app/src/trueskill_model.py.

El origen usa la librería `trueskill`. Aquí se porta el caso 1v1 (un equipo por
lado) en Python puro con `statistics.NormalDist` (sin scipy, sin dependencia
extra), fiel a las ecuaciones de actualización de TrueSkill (Herbrich et al.;
forma cerrada de Moserware "Computing Your Skill"). Maneja empates de forma nativa.

Validado numéricamente contra la librería `trueskill` (ver tests).

  P(A gana) = Φ( (μ_A − μ_B) / sqrt(2β² + σ_A² + σ_B²) )
  expose    = μ − 3σ   (rating conservador)
  semilla   = μ = 25 + (Elo − mean_elo)/elo_per_mu ;  σ = σ0
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist

_N = NormalDist()
_TINY = 1e-12

# Constantes por defecto de TrueSkill (idénticas a la lib).
MU0 = 25.0
SIGMA0 = 25.0 / 3.0
BETA = SIGMA0 / 2.0
TAU = SIGMA0 / 100.0
DEFAULT_DRAW_PROBABILITY = 0.26  # ~empates en fase de grupos de un Mundial


def _pdf(x: float) -> float:
    return _N.pdf(x)


def _cdf(x: float) -> float:
    return _N.cdf(x)


# ── Funciones V/W (truncamiento gaussiano) ───────────────────────────────────


def _v_win(t: float, e: float) -> float:
    denom = _cdf(t - e)
    if denom < _TINY:
        return -(t - e)
    return _pdf(t - e) / denom


def _w_win(t: float, e: float) -> float:
    denom = _cdf(t - e)
    if denom < _TINY:
        return 1.0 if (t - e) < 0 else 0.0
    v = _v_win(t, e)
    return v * (v + t - e)


def _v_draw(t: float, e: float) -> float:
    abs_t = abs(t)
    denom = _cdf(e - abs_t) - _cdf(-e - abs_t)
    if denom < _TINY:
        return (-t) if t < 0 else t
    numer = _pdf(-e - abs_t) - _pdf(e - abs_t)
    return (-numer if t < 0 else numer) / denom


def _w_draw(t: float, e: float) -> float:
    abs_t = abs(t)
    denom = _cdf(e - abs_t) - _cdf(-e - abs_t)
    if denom < _TINY:
        return 1.0
    v = _v_draw(t, e)
    return v * v + (
        (e - abs_t) * _pdf(e - abs_t) - (-e - abs_t) * _pdf(-e - abs_t)
    ) / denom


@dataclass
class Rating:
    mu: float = MU0
    sigma: float = SIGMA0


@dataclass
class TrueSkillSystem:
    draw_probability: float = DEFAULT_DRAW_PROBABILITY
    beta: float = BETA
    tau: float = TAU
    elo_per_mu: float = 40.0
    mean_elo: float = 1500.0
    ratings: dict[str, Rating] = field(default_factory=dict)

    def _draw_margin(self) -> float:
        return _N.inv_cdf((self.draw_probability + 1.0) / 2.0) * math.sqrt(2.0) * self.beta

    def seed_from_elo(self, initial_elo: dict[str, float]) -> None:
        self.ratings = {
            team: Rating(mu=MU0 + (elo - self.mean_elo) / self.elo_per_mu, sigma=SIGMA0)
            for team, elo in initial_elo.items()
        }

    def get(self, team: str) -> Rating:
        return self.ratings.get(team) or Rating()

    def expose(self, team: str) -> float:
        r = self.get(team)
        return r.mu - 3.0 * r.sigma

    def win_probability(self, home: str, away: str) -> float:
        a, b = self.get(home), self.get(away)
        denom = math.sqrt(2.0 * self.beta ** 2 + a.sigma ** 2 + b.sigma ** 2)
        if denom == 0:
            return 0.5
        return _cdf((a.mu - b.mu) / denom)

    def update_match(self, home: str, away: str, hg: int, ag: int) -> None:
        rh, ra = self.get(home), self.get(away)
        # dinámica: se añade tau² a la varianza antes de cada partido
        sh2 = rh.sigma ** 2 + self.tau ** 2
        sa2 = ra.sigma ** 2 + self.tau ** 2
        c = math.sqrt(2.0 * self.beta ** 2 + sh2 + sa2)
        e = self._draw_margin() / c

        if hg == ag:  # empate (nativo)
            t = (rh.mu - ra.mu) / c
            v, w = _v_draw(t, e), _w_draw(t, e)
            new_h = Rating(rh.mu + (sh2 / c) * v, math.sqrt(sh2 * (1.0 - (sh2 / c ** 2) * w)))
            new_a = Rating(ra.mu - (sa2 / c) * v, math.sqrt(sa2 * (1.0 - (sa2 / c ** 2) * w)))
            self.ratings[home], self.ratings[away] = new_h, new_a
            return

        # gana uno: recalcular con el ganador primero
        if hg > ag:
            (wn, wn2), (ls, ls2), wk, lk = (rh, sh2), (ra, sa2), home, away
        else:
            (wn, wn2), (ls, ls2), wk, lk = (ra, sa2), (rh, sh2), away, home
        t = (wn.mu - ls.mu) / c
        v, w = _v_win(t, e), _w_win(t, e)
        self.ratings[wk] = Rating(wn.mu + (wn2 / c) * v, math.sqrt(wn2 * (1.0 - (wn2 / c ** 2) * w)))
        self.ratings[lk] = Rating(ls.mu - (ls2 / c) * v, math.sqrt(ls2 * (1.0 - (ls2 / c ** 2) * w)))
