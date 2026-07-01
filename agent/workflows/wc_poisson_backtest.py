"""Backtest de calibración/skill del modelo Poisson de goles.

NO hay líneas O/U históricas de mercado (Polymarket sólo expone las live; worldcup.db
sólo tenía moneyline). Sin línea no se puede medir "beat the line". Lo que SÍ se puede
medir, y es lo honesto, es si las probabilidades de goles del modelo tienen SKILL:
predicen mejor que el promedio (base rate) fuera de muestra.

Método (predict-then-update, ventana expansiva):
  - Recorre los partidos en orden cronológico.
  - Para cada uno, re-ajusta el Poisson SOLO con los partidos previos y predice
    P(Over k.5) y P(BTTS); luego compara contra el resultado real.
  - Sólo evalúa si ambos equipos ya tienen >= min_team partidos previos (probar la
    señal por-equipo, no el promedio de liga) y hay >= warmup partidos para fijar
    la tasa base.
  - Baseline: el base rate corriente (fracción de partidos previos que fueron Over/
    BTTS). Si el modelo no le gana al base rate, no tiene skill.

Métricas por mercado: Brier, log-loss, accuracy (umbral 0.5) y Brier Skill Score
(BSS = 1 - brier_modelo/brier_base; >0 = el modelo aporta).
"""
from __future__ import annotations

import math

from adapters.football.wc_poisson import PoissonGoalsModel
from adapters.football.wc_poisson_pipeline import load_goal_matches

MARKETS = {
    "Over 1.5": ("over", 1.5),
    "Over 2.5": ("over", 2.5),
    "Over 3.5": ("over", 3.5),
    "BTTS": ("btts", None),
}
_EPS = 1e-9


def _actual(kind: str, line: float | None, hg: int, ag: int) -> int:
    if kind == "over":
        return 1 if (hg + ag) >= math.floor(line) + 1 else 0
    return 1 if (hg >= 1 and ag >= 1) else 0


def _model_p(kind: str, line: float | None, fc) -> float:
    return fc.prob_over(line) if kind == "over" else fc.prob_btts()


def backtest(matches: list[tuple[str, str, int, int]], *, shrink_k: float = 5.0,
             min_team: int = 2, warmup: int = 20) -> dict:
    """Devuelve métricas por mercado + el detalle de predicciones evaluadas."""
    appearances: dict[str, int] = {}
    # acumuladores por mercado
    acc = {name: {"n": 0, "brier_m": 0.0, "brier_b": 0.0, "ll_m": 0.0,
                  "hit_m": 0, "hit_b": 0, "pos": 0} for name in MARKETS}
    rows: list[dict] = []

    for idx, (h, a, hg, ag) in enumerate(matches):
        ready = (idx >= warmup and appearances.get(h, 0) >= min_team
                 and appearances.get(a, 0) >= min_team)
        if ready:
            past = matches[:idx]
            model = PoissonGoalsModel(shrink_k=shrink_k).fit(past)
            fc = model.forecast(h, a)
            row = {"home": h, "away": a, "hg": hg, "ag": ag, "total": hg + ag}
            for name, (kind, line) in MARKETS.items():
                p = min(1 - _EPS, max(_EPS, _model_p(kind, line, fc)))
                y = _actual(kind, line, hg, ag)
                base = sum(_actual(kind, line, x[2], x[3]) for x in past) / len(past)
                base = min(1 - _EPS, max(_EPS, base))
                s = acc[name]
                s["n"] += 1
                s["pos"] += y
                s["brier_m"] += (p - y) ** 2
                s["brier_b"] += (base - y) ** 2
                s["ll_m"] += -(y * math.log(p) + (1 - y) * math.log(1 - p))
                s["hit_m"] += int((p >= 0.5) == bool(y))
                s["hit_b"] += int((base >= 0.5) == bool(y))
                row[name] = {"p": round(p, 3), "base": round(base, 3), "y": y}
            rows.append(row)
        appearances[h] = appearances.get(h, 0) + 1
        appearances[a] = appearances.get(a, 0) + 1

    out = {}
    for name, s in acc.items():
        n = s["n"] or 1
        bm, bb = s["brier_m"] / n, s["brier_b"] / n
        out[name] = {
            "n": s["n"],
            "base_rate": round(s["pos"] / n, 3),
            "brier_model": round(bm, 4),
            "brier_base": round(bb, 4),
            "bss": round(1 - bm / bb, 4) if bb > 0 else 0.0,   # >0 = el modelo aporta
            "logloss_model": round(s["ll_m"] / n, 4),
            "acc_model": round(s["hit_m"] / n, 3),
            "acc_base": round(s["hit_b"] / n, 3),
        }
    return {"markets": out, "n_eval": len(rows), "rows": rows}
