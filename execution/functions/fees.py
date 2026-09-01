"""Cálculo puro de la comisión taker de Polymarket."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from core.utils import to_decimal


def taker_fee_usdc(shares: Decimal | float, price: Decimal | float,
                   fee_rate_bps: int) -> Decimal:
    """``shares × rate × price × (1-price)``, redondeado a 5 decimales."""
    quantity, p = to_decimal(shares), to_decimal(price)
    if quantity < 0 or not Decimal(0) <= p <= Decimal(1) or fee_rate_bps < 0:
        raise ValueError("shares, price o fee_rate_bps inválidos")
    rate = Decimal(fee_rate_bps) / Decimal(10_000)
    return (quantity * rate * p * (Decimal(1) - p)).quantize(
        Decimal("0.00001"), rounding=ROUND_HALF_UP)
