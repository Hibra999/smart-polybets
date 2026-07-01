"""Fuente de cuenta live de Polymarket. Adapter SDK V2 detrás de un Protocol.

Patrón stub-inyectable (como research.PolymarketLiveSource / execution.PolymarketBroker):
la lógica pura consume el Protocol y se testea con un fake; el adapter real
`PolymarketAccountSource` es el borde delgado que requiere el SDK oficial V2
(`polymarket-client`) + private key. Sin ellos, lanza AccountUnavailableError.
"""
from __future__ import annotations

import os
from typing import Protocol

from core.exceptions import AccountUnavailableError
from portfolio.schemas.account import AccountBalance, LivePosition, OpenOrder


class AccountSource(Protocol):
    def get_balance(self) -> AccountBalance: ...
    def get_positions(self) -> list[LivePosition]: ...
    def get_open_orders(self) -> list[OpenOrder]: ...


class PolymarketAccountSource:
    """Adapter live: lee la cuenta vía el SDK oficial V2 (polymarket-client)."""

    def __init__(self, *, private_key: str | None = None, funder: str | None = None) -> None:
        self._private_key = private_key if private_key is not None else (
            os.getenv("POLYMARKET_PRIVATE_KEY") or ""
        )
        self._funder = funder or os.getenv("POLYMARKET_FUNDER") or None
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not self._private_key:
            raise AccountUnavailableError(
                "Falta POLYMARKET_PRIVATE_KEY para leer la cuenta live."
            )
        try:
            import polymarket_client  # noqa: F401  # TODO(wiring-sdk): confirmar nombre real
        except ImportError as exc:
            raise AccountUnavailableError(
                'SDK live no instalado. Corre: pip install --pre -e ".[live]"'
            ) from exc
        # TODO(wiring-sdk): construir el cliente V2 real con self._private_key/self._funder.
        raise AccountUnavailableError("Adapter SDK V2 pendiente de wiring (TODO).")

    def get_balance(self) -> AccountBalance:
        self._ensure_client()
        raise NotImplementedError  # TODO(wiring-sdk)

    def get_positions(self) -> list[LivePosition]:
        self._ensure_client()
        raise NotImplementedError  # TODO(wiring-sdk)

    def get_open_orders(self) -> list[OpenOrder]:
        self._ensure_client()
        raise NotImplementedError  # TODO(wiring-sdk)
