"""Carga de predicciones del modelo del torneo.

Resuelve el adapter del torneo desde tournaments/registry.py y le pide la
predicción. NUNCA hardcodea tournament_id — siempre lo recibe explícito.
"""
from __future__ import annotations

from research.schemas.match_prediction import MatchPrediction


def get_event_prediction(event_id: str, tournament_id: str) -> MatchPrediction | None:
    """MatchPrediction del evento, o None si el modelo no tiene predicción.

    Si el modelo no predice (evento inexistente, sin Elo, etc.) retorna None —
    no se inventa probabilidad.
    """
    from tournaments.registry import get_adapter  # import tardío evita ciclo

    adapter = get_adapter(tournament_id)
    return adapter.get_event_prediction(event_id)
