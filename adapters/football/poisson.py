"""Modelo Poisson básico de goles para ligas de fútbol.

Es un modelo SEPARADO y COMPLEMENTARIO: no reemplaza ni toca a Elo/Bayes/TrueSkill
(que predicen el GANADOR). Este predice GOLES, para abrir mercados de otro tipo:
Over/Under total, Both Teams To Score (BTTS), 1X2 derivado de goles y marcadores
exactos.

Modelo (Poisson independiente, el clásico "basic Poisson"):
  base        = goles promedio que un equipo anota por partido en el torneo
  attack_i    = (goles que anota i / partido) / base        (>1 anota mas que la media)
  defense_i   = (goles que concede i / partido) / base      (>1 defiende peor que la media)
  lambda_home = base * attack_home * defense_away * sqrt(home_factor)
  lambda_away = base * attack_away * defense_home / sqrt(home_factor)
  goles_home ~ Poisson(lambda_home),  goles_away ~ Poisson(lambda_away)   (independientes)

Con muestras pequeñas las tasas se encogen
(shrinkage empírico-bayesiano) hacia la media de la liga con un pseudo-conteo
`shrink_k`: equipos con pocos partidos quedan cerca del promedio en vez de explotar
por un único resultado extremo.

Puro: no toca la DB. La carga de partidos la hace ``poisson_pipeline``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

# Cota superior de goles por equipo para construir la grilla de marcadores. P(>10)
# bajo cualquier lambda realista de futbol es despreciable.
MAX_GOALS = 10


def poisson_pmf(lmbda: float, k: int) -> float:
    """P(X = k) con X ~ Poisson(lmbda)."""
    if lmbda <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lmbda) * lmbda ** k / math.factorial(k)


@dataclass(frozen=True)
class TeamRates:
    attack: float    # fuerza ofensiva relativa (1.0 = media de la liga)
    defense: float   # fragilidad defensiva relativa (1.0 = media; >1 concede mas)
    matches: int     # partidos reales usados para estimarla (gobierna el shrinkage)


@dataclass
class GoalsForecast:
    """Pronóstico de goles de un partido y las probabilidades de mercado derivadas."""
    home: str
    away: str
    lambda_home: float
    lambda_away: float
    matches_home: int
    matches_away: int

    @property
    def expected_total(self) -> float:
        return self.lambda_home + self.lambda_away

    def score_matrix(self, max_goals: int = MAX_GOALS) -> list[list[float]]:
        ph = [poisson_pmf(self.lambda_home, i) for i in range(max_goals + 1)]
        pa = [poisson_pmf(self.lambda_away, j) for j in range(max_goals + 1)]
        return [[ph[i] * pa[j] for j in range(max_goals + 1)] for i in range(max_goals + 1)]

    def prob_over(self, line: float = 2.5, max_goals: int = MAX_GOALS) -> float:
        """P(goles totales > line). line típico .5 (over) evita empates de línea."""
        m = self.score_matrix(max_goals)
        need = math.floor(line) + 1  # over 2.5 -> total >= 3
        return sum(m[i][j] for i in range(max_goals + 1) for j in range(max_goals + 1)
                   if i + j >= need)

    def prob_under(self, line: float = 2.5, max_goals: int = MAX_GOALS) -> float:
        return 1.0 - self.prob_over(line, max_goals)

    def prob_btts(self) -> float:
        """P(ambos equipos anotan) = (1 - P(home=0)) * (1 - P(away=0))."""
        return (1.0 - math.exp(-self.lambda_home)) * (1.0 - math.exp(-self.lambda_away))

    def prob_result(self, max_goals: int = MAX_GOALS) -> dict[str, float]:
        """1X2 derivado de la grilla de goles (cross-check del match-winner)."""
        m = self.score_matrix(max_goals)
        home = draw = away = 0.0
        for i in range(max_goals + 1):
            for j in range(max_goals + 1):
                if i > j:
                    home += m[i][j]
                elif i == j:
                    draw += m[i][j]
                else:
                    away += m[i][j]
        return {"home": home, "draw": draw, "away": away}

    def top_scores(self, n: int = 5, max_goals: int = MAX_GOALS) -> list[tuple[int, int, float]]:
        m = self.score_matrix(max_goals)
        cells = [(i, j, m[i][j]) for i in range(max_goals + 1) for j in range(max_goals + 1)]
        cells.sort(key=lambda c: c[2], reverse=True)
        return cells[:n]

    def confidence(self, *, high_at: int = 6, low_below: int = 3) -> str:
        """Confianza por el respaldo de datos del lado más flaco."""
        n = min(self.matches_home, self.matches_away)
        if n >= high_at:
            return "HIGH"
        if n < low_below:
            return "LOW"
        return "MEDIUM"


@dataclass
class PoissonGoalsModel:
    """Ajusta tasas de ataque/defensa por equipo y pronostica goles.

    ``neutral=False`` aplica el factor de localía estimado. ``neutral=True`` queda
    disponible para competiciones sin localía real.
    """
    shrink_k: float = 5.0          # pseudo-partidos al promedio (encoge tasas finas)
    neutral: bool = False          # ligas: aplica ventaja local estimada
    base: float = 1.30             # goles/equipo/partido (se recalcula en fit)
    home_factor: float = 1.0       # cociente goles_local/goles_visita de la liga (diagnóstico)
    rates: dict[str, TeamRates] = field(default_factory=dict)
    fitted: bool = False

    def fit(self, matches: list[tuple[str, str, int, int]]) -> PoissonGoalsModel:
        """matches: (home, away, home_goals, away_goals) reales ya jugados.

        Calcula la media de la liga, las tasas crudas por equipo y las encoge hacia
        1.0 con pseudo-conteo `shrink_k`."""
        played = [(h, a, hg, ag) for (h, a, hg, ag) in matches
                  if hg is not None and ag is not None]
        n = len(played)
        if n == 0:
            self.fitted = True
            return self

        sum_home = sum(hg for _, _, hg, _ in played)
        sum_away = sum(ag for _, _, _, ag in played)
        total = sum_home + sum_away
        self.base = total / (2 * n)                       # goles/equipo/partido
        home_avg = sum_home / n
        away_avg = sum_away / n
        self.home_factor = (home_avg / away_avg) if away_avg > 0 else 1.0

        scored: dict[str, int] = {}
        conceded: dict[str, int] = {}
        played_n: dict[str, int] = {}
        for h, a, hg, ag in played:
            scored[h] = scored.get(h, 0) + hg
            conceded[h] = conceded.get(h, 0) + ag
            scored[a] = scored.get(a, 0) + ag
            conceded[a] = conceded.get(a, 0) + hg
            played_n[h] = played_n.get(h, 0) + 1
            played_n[a] = played_n.get(a, 0) + 1

        base = self.base or 1.0
        k = self.shrink_k
        self.rates = {}
        for team, np_ in played_n.items():
            # rate encogida = (goles + k*base) / (partidos + k); attack = rate/base
            atk = (scored[team] + k * base) / (np_ + k) / base
            dfn = (conceded[team] + k * base) / (np_ + k) / base
            self.rates[team] = TeamRates(attack=atk, defense=dfn, matches=np_)
        self.fitted = True
        return self

    def team(self, name: str) -> TeamRates:
        """Tasas de un equipo; media de la liga (1.0) si no tiene historial."""
        return self.rates.get(name, TeamRates(attack=1.0, defense=1.0, matches=0))

    def forecast(self, home: str, away: str) -> GoalsForecast:
        rh, ra = self.team(home), self.team(away)
        # En sede neutral hf=1 reparte parejo.
        hf = 1.0 if self.neutral else (
            math.sqrt(self.home_factor) if self.home_factor > 0 else 1.0)
        lam_home = self.base * rh.attack * ra.defense * hf
        lam_away = self.base * ra.attack * rh.defense / hf
        return GoalsForecast(
            home=home, away=away,
            lambda_home=lam_home, lambda_away=lam_away,
            matches_home=rh.matches, matches_away=ra.matches,
        )
