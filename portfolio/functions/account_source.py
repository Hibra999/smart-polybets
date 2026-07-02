"""Fuente de cuenta live de Polymarket. Adapter delegando en PolymarketGateway.

Reimplementado en Task 1.3: delega en `PolymarketGateway` en lugar de duplicar la
lógica de cliente. El contrato público (Protocol `AccountSource`, clase, constructores,
excepción `AccountUnavailableError`) se preserva íntegro.
"""
from __future__ import annotations

from typing import Protocol

from core.exceptions import AccountUnavailableError  # noqa: F401 — re-export para callers
from portfolio.schemas.account import (
    AccountBalance,
    ClosedPositionLive,
    LivePosition,
    OpenOrder,
)
from venue.gateway import PolymarketGateway


class AccountSource(Protocol):
    def get_balance(self) -> AccountBalance: ...
    def get_positions(self) -> list[LivePosition]: ...
    def get_open_orders(self) -> list[OpenOrder]: ...
    def get_closed_positions(self, limit: int = 6) -> list[ClosedPositionLive]: ...


class PolymarketAccountSource:
    """Adapter live: lee la cuenta vía PolymarketGateway (SDK oficial V2)."""

    def __init__(self, *, private_key: str | None = None, funder: str | None = None) -> None:
        self._gateway = PolymarketGateway(private_key=private_key, funder=funder)

    @property
    def wallet(self) -> str | None:
        client = self._gateway._ensure_client()
        return getattr(client, "wallet", None)

    # ── lecturas (read-only) — AccountUnavailableError si falta key/SDK ───────

    def get_balance(self) -> AccountBalance:
        return self._gateway.balance()

    def get_positions(self) -> list[LivePosition]:
        return self._gateway.positions()

    def get_open_orders(self) -> list[OpenOrder]:
        return self._gateway.open_orders()

    def get_closed_positions(self, limit: int = 6) -> list[ClosedPositionLive]:
        return self._gateway.closed_positions(limit)
