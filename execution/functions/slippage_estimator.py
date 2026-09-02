"""Estimación de slippage dado el orderbook. Función pura.

El orderbook se inyecta como lista de niveles (price, size_shares_disponibles),
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
    if size <= 0:
        raise ValueError("size_usdc debe ser positivo")
    if not orderbook:
        return SlippageEstimate(
            token_id=token_id, size_usdc=size, expected_avg_price=None,
            slippage_pct=Decimal(0), fully_filled=False,
            note="sin orderbook (stub): wire CLOB API para estimación real",
        )

    levels = [
        (to_decimal(price), to_decimal(available_shares))
        for price, available_shares in orderbook
        if Decimal(0) < to_decimal(price) < Decimal(1)
        and to_decimal(available_shares) > 0
    ]
    if not levels:
        return SlippageEstimate(
            token_id=token_id, size_usdc=size, expected_avg_price=None,
            slippage_pct=Decimal(0), fully_filled=False, note="libro vacío",
        )

    best_price = levels[0][0]
    remaining = size
    spent = Decimal(0)
    shares = Decimal(0)
    for price_d, available_d in levels:
        take_usdc = min(remaining, price_d * available_d)
        spent += take_usdc
        shares += take_usdc / price_d
        remaining -= take_usdc
        if remaining <= 0:
            break

    if shares <= 0:
        return SlippageEstimate(
            token_id=token_id, size_usdc=size, expected_avg_price=None,
            slippage_pct=Decimal(0), fully_filled=False, note="libro vacío",
        )

    avg = spent / shares
    slippage = (avg - best_price) / best_price if best_price > 0 else Decimal(0)
    return SlippageEstimate(
        token_id=token_id, size_usdc=size, expected_avg_price=avg,
        slippage_pct=slippage, fully_filled=remaining <= 0,
    )
