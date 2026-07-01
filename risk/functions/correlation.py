"""Estimación de correlación con posiciones abiertas. Función pura, heurística.

No es una correlación estadística rigurosa (no hay serie de precios en este
contexto) sino una heurística de solapamiento: posiciones sobre el mismo evento
o el mismo participante están altamente correlacionadas.
"""
from __future__ import annotations

from research.schemas.market_opportunity import MarketOpportunity
from portfolio.schemas.position import Position


def estimate_correlation(
    opportunity: MarketOpportunity, open_positions: list[Position]
) -> float:
    """Correlación estimada [0,1] de la oportunidad con el libro abierto."""
    if not open_positions:
        return 0.0

    participants = {opportunity.participant_home, opportunity.participant_away}
    max_corr = 0.0
    for pos in open_positions:
        if pos.condition_id == opportunity.polymarket_condition_id:
            max_corr = max(max_corr, 1.0)          # mismo mercado
        elif pos.participant in participants:
            max_corr = max(max_corr, 0.8)          # mismo participante
        elif pos.tournament_id == opportunity.tournament_id:
            max_corr = max(max_corr, 0.2)          # mismo torneo, contexto compartido
    return max_corr
