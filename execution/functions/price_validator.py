"""Validación del precio live vs el precio de la señal. Función pura.

El precio live se inyecta (no hay red en esta capa). Si se movió más allá de la
tolerancia, NO se reintenta automáticamente: se reporta para re-evaluar desde
research/.
"""
from __future__ import annotations

from decimal import Decimal

from core.utils import to_decimal


def validate_live_price(
    signal_price: Decimal | float,
    live_price: Decimal | float,
    tolerance: Decimal | float = Decimal("0.02"),
) -> bool:
    """True si |live - signal| / signal <= tolerance."""
    signal = to_decimal(signal_price)
    live = to_decimal(live_price)
    if signal <= 0:
        return False
    return abs(live - signal) / signal <= to_decimal(tolerance)
