"""Carga de la probabilidad de resultado (1X2) del modelo Poisson para un fixture.

I/O aislado aquí (lee el SQLite vía el loader del Poisson y el fixture vía el reader).
Devuelve {"home","draw","away"} o None si no hay datos — no se inventa probabilidad.
El pipeline Poisson se cachea por tournament_id por proceso (fit es caro).
"""
from __future__ import annotations

import logging

from adapters.football.db_reader import FootballDBReader
from adapters.football.wc_poisson_pipeline import WorldCupPoissonPipeline

logger = logging.getLogger(__name__)

_PIPELINE_CLS = WorldCupPoissonPipeline   # indirección para tests
_READER_CLS = FootballDBReader
_CACHE: dict[str, object] = {}


def _pipeline(tournament_id: str):
    pipe = _CACHE.get(tournament_id)
    if pipe is None:
        pipe = _PIPELINE_CLS(tournament_id).fit()
        _CACHE[tournament_id] = pipe
    return pipe


def match_result_probs(tournament_id: str, event_id: str) -> dict[str, float] | None:
    try:
        fx = _READER_CLS(tournament_id).get_fixture(event_id)
        if fx is None:
            return None
        home_id, away_id = fx["home_team_id"], fx["away_team_id"]
        r = _pipeline(tournament_id).forecast(home_id, away_id).prob_result()
        total = float(r.get("home", 0)) + float(r.get("draw", 0)) + float(r.get("away", 0))
        if total <= 0:
            return None
        return {"home": float(r["home"]), "draw": float(r["draw"]), "away": float(r["away"])}
    except Exception:
        # Fail-safe (no se inventa prob), pero dejamos rastro: un adapter regresado
        # silenciaría toda la estrategia double_chance sin señal.
        logger.warning("poisson_loader falló tournament=%s event=%s",
                       tournament_id, event_id, exc_info=True)
        return None
