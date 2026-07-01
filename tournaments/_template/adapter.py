"""Plantilla de adapter de torneo.

Apunta al SQLite del torneo en `data/{tournament_id}/`. En la práctica el
adapter concreto se resuelve desde `tournaments/registry.py`; este módulo es el
punto de personalización por torneo (ej: home_advantage específico, overrides).
"""
from __future__ import annotations

TOURNAMENT_ID = "{tournament_id}"
SPORT = "{sport}"


def build_adapter():
    """Devuelve el SportAdapter de este torneo (delega en el registry)."""
    from tournaments.registry import get_adapter
    return get_adapter(TOURNAMENT_ID)
