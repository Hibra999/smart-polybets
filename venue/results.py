"""Reconstrucción PURA de marcadores desde mercados resueltos de Polymarket.

Dos estrategias, en orden de preferencia:
  1. `score_from_exact_markets`: mercado "Exact Score: {H} n - m {A}?" resuelto
     Yes → marcador directo (Liga MX y ligas nuevas de PM lo tienen).
  2. `score_from_ou_ladder`: escalera per-team "{H} vs. {A}: {Team} O/U N.5" +
     total "{H} vs. {A}: O/U N.5" (formato del Mundial 2026).

Sin red: reciben Market-like objects (atributos vía getattr) → unit-testeables.
Extraído de scripts/update_results.py al generalizarlo (2026-07-14).
"""
from __future__ import annotations

import re

from venue.matching import canon

_EXACT = re.compile(r"^Exact Score:\s*(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+?)\?*$", re.I)
_TEAM_OU = re.compile(r":\s*(.+?)\s+O/U\s+(\d\.5)$")
_TOTAL_OU = re.compile(r":\s*O/U\s+(\d\.5)$")


def resolved_label(mk) -> str | None:
    """Label del outcome resuelto (precio ~1) de un Market del SDK, o None."""
    outs = getattr(mk, "outcomes", None)
    if outs is None:
        return None
    for oc in (getattr(outs, "yes", None), getattr(outs, "no", None)):
        if oc is not None and oc.price is not None and float(oc.price) > 0.98:
            return oc.label
    return None


def score_from_exact_markets(markets, home_disp: str, away_disp: str) -> tuple[int, int] | None:
    """(home_goals, away_goals) del mercado Exact Score resuelto Yes, o None."""
    hk, ak = canon(home_disp), canon(away_disp)
    for mk in markets or []:
        q = str(getattr(mk, "question", "") or "")
        m = _EXACT.match(q)
        if not m:
            continue
        lab = resolved_label(mk)
        if lab is None or lab.lower() != "yes":
            continue
        t1, g1, g2, t2 = canon(m.group(1)), int(m.group(2)), int(m.group(3)), canon(m.group(4))
        if t1 == hk and t2 == ak:
            return g1, g2
        if t1 == ak and t2 == hk:
            return g2, g1
    return None


def _bracket(over_lines: list[float], under_lines: list[float]) -> tuple[int, int]:
    lo = max([int(x) + 1 for x in over_lines], default=0)
    hi = min([int(x) for x in under_lines], default=99)
    return lo, hi


def score_from_ou_ladder(markets, home_disp: str, away_disp: str) -> tuple[int | None, int | None]:
    """Reconstruye (home_goals, away_goals) desde la escalera O/U resuelta.

    Per-team hasta 2.5; si un equipo marcó 3+ se fija con el total del partido
    menos los goles del rival (formato Mundial 2026).
    """
    team_over: dict[str, list[float]] = {}
    team_under: dict[str, list[float]] = {}
    tot_over: list[float] = []
    tot_under: list[float] = []
    for mk in markets or []:
        q = str(getattr(mk, "question", "") or "")
        if "Half" in q:
            continue
        lab = resolved_label(mk)
        if lab is None:
            continue
        over = lab.lower() == "over"
        mteam = _TEAM_OU.search(q)
        mtot = _TOTAL_OU.search(q)
        if mteam:
            team, line = mteam.group(1), float(mteam.group(2))
            (team_over if over else team_under).setdefault(team, []).append(line)
        elif mtot:
            (tot_over if over else tot_under).append(float(mtot.group(1)))

    def team_goals(disp: str):
        key = next((t for t in set(team_over) | set(team_under) if canon(t) == canon(disp)), None)
        if key is None:
            return None
        lo, hi = _bracket(team_over.get(key, []), team_under.get(key, []))
        return lo if lo == hi else (lo, hi)

    hg = team_goals(home_disp)
    ag = team_goals(away_disp)
    tlo, thi = _bracket(tot_over, tot_under)
    total = tlo if tlo == thi else None

    def pin(val, other):
        if isinstance(val, tuple):  # rango (ej. 3+): fijar con total - rival
            if total is not None and isinstance(other, int):
                return total - other
            return val[0]  # piso como fallback
        return val

    hg2 = pin(hg, ag if isinstance(ag, int) else None)
    ag2 = pin(ag, hg if isinstance(hg, int) else None)
    return hg2, ag2


def reconstruct_score(markets, home_disp: str, away_disp: str) -> tuple[int | None, int | None]:
    """Marcador final: Exact Score si existe resuelto; si no, escalera O/U."""
    exact = score_from_exact_markets(markets, home_disp, away_disp)
    if exact is not None:
        return exact
    return score_from_ou_ladder(markets, home_disp, away_disp)
