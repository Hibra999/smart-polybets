"""Kelly fraccional. Función pura.

Para una apuesta binaria en Polymarket al precio `price` (costo por share que
paga 1 si gana):
    odds netas  b = (1 - price) / price
    f*          = p - (1 - p) / b          (fracción Kelly completa)
    aplicada    = max(0, f*) * fraction_multiplier
    size        = aplicada * bankroll

Se topa por `max_bet_usdc` y por `max_kelly_fraction` (cap de fracción del
bankroll). Nunca devuelve tamaño negativo.
"""
from __future__ import annotations

from decimal import Decimal

from core.utils import quantize_usdc, to_decimal
from risk.schemas.kelly_output import KellyOutput

_ZERO = Decimal("0")
_ONE = Decimal("1")


def fractional_kelly(
    win_probability: Decimal | float,
    price: Decimal | float,
    fraction_multiplier: Decimal | float,
    bankroll_usdc: Decimal | float,
    *,
    max_bet_usdc: Decimal | float | None = None,
    max_kelly_fraction: Decimal | float | None = None,
) -> KellyOutput:
    p = to_decimal(win_probability)
    price = to_decimal(price)
    mult = to_decimal(fraction_multiplier)
    bankroll = to_decimal(bankroll_usdc)

    notes: list[str] = []

    if not (_ZERO < price < _ONE):
        return KellyOutput(
            raw_kelly=_ZERO, kelly_fraction=_ZERO, fraction_multiplier=mult,
            recommended_size_usdc=_ZERO, bankroll_usdc=bankroll, capped=False,
            notes=[f"precio fuera de (0,1): {price}"],
        )

    b = (_ONE - price) / price  # odds netas
    raw_kelly = p - (_ONE - p) / b
    if raw_kelly < _ZERO:
        raw_kelly = _ZERO
        notes.append("edge negativo: Kelly=0")

    applied_fraction = raw_kelly * mult

    capped = False
    if max_kelly_fraction is not None:
        cap = to_decimal(max_kelly_fraction)
        if applied_fraction > cap:
            applied_fraction = cap
            capped = True
            notes.append(f"fracción topada a max_kelly_fraction={cap}")

    size = applied_fraction * bankroll
    if max_bet_usdc is not None:
        mb = to_decimal(max_bet_usdc)
        if size > mb:
            size = mb
            capped = True
            notes.append(f"tamaño topado a max_bet_usdc={mb}")

    return KellyOutput(
        raw_kelly=raw_kelly,
        kelly_fraction=applied_fraction,
        fraction_multiplier=mult,
        recommended_size_usdc=quantize_usdc(size),
        bankroll_usdc=bankroll,
        capped=capped,
        notes=notes,
    )
