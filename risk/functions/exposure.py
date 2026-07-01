"""Exposición por participante. Funciones puras."""
from __future__ import annotations

from decimal import Decimal

from core.utils import to_decimal
from portfolio.schemas.portfolio_state import PortfolioState

_ZERO = Decimal("0")


def projected_exposure_pct(
    portfolio_state: PortfolioState, participant: str, additional_size_usdc: Decimal | float
) -> Decimal:
    """Exposición proyectada (fracción del bankroll) al participante si se abre la posición."""
    bankroll = portfolio_state.bankroll_usdc
    current = portfolio_state.exposure_for(participant)
    if bankroll <= _ZERO:
        return Decimal("1")  # sin bankroll, cualquier exposición es 100%+
    add_frac = to_decimal(additional_size_usdc) / bankroll
    return current + add_frac


def check_participant_exposure(
    portfolio_state: PortfolioState,
    participant: str,
    additional_size_usdc: Decimal | float,
    threshold: Decimal | float,
) -> bool:
    """True si la exposición proyectada queda DENTRO del límite (< threshold)."""
    return projected_exposure_pct(portfolio_state, participant, additional_size_usdc) < to_decimal(
        threshold
    )
