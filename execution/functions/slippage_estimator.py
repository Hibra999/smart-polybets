"""Estimación de slippage dado el orderbook. Función pura.

El orderbook se inyecta como lista de niveles (price, size_usdc_disponible),
ordenados del mejor precio al peor. Sin orderbook → slippage 0 con nota (stub).
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from core.utils import to_decimal


class SlippageEstimate(BaseModel):
    model_config = ConfigDict(frozen=True)

    token_id: str
    size_usdc: Decimal
    expected_avg_price: Decimal | None
    slippage_pct: Decimal           # vs el mejor precio del libro
    fully_filled: bool
    note: str | None = None


def estimate(
    token_id: str,
    size_usdc: Decimal | float,
    *,
    orderbook: list[tuple[float, float]] | None = None,
) -> SlippageEstimate:
    size = to_decimal(size_usdc)
    if not orderbook:
        return SlippageEstimate(
            token_id=token_id, size_usdc=size, expected_avg_price=None,
            slippage_pct=Decimal("0"), fully_filled=False,
            note="sin orderbook (stub): wire CLOB API para estimación real",
        )

    best_price = to_decimal(orderbook[0][0])
    remaining = size
    cost = Decimal("0")
    filled = Decimal("0")
    for price, avail in orderbook:
        price_d, avail_d = to_decimal(price), to_decimal(avail)
        take = min(remaining, avail_d)
        cost += take * price_d
        filled += take
        remaining -= take
        if remaining <= 0:
            break

    if filled <= 0:
        return SlippageEstimate(
            token_id=token_id, size_usdc=size, expected_avg_price=None,
            slippage_pct=Decimal("0"), fully_filled=False, note="libro vacío",
        )

    avg = cost / filled
    slippage = (avg - best_price) / best_price if best_price > 0 else Decimal("0")
    return SlippageEstimate(
        token_id=token_id, size_usdc=size, expected_avg_price=avg,
        slippage_pct=slippage, fully_filled=remaining <= 0,
    )
