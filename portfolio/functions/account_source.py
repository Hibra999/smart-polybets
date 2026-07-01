"""Fuente de cuenta live de Polymarket. Adapter SDK V2 detrás de un Protocol.

Patrón stub-inyectable (como research.PolymarketLiveSource / execution.PolymarketBroker):
la lógica pura consume el Protocol y se testea con un fake; el adapter real
`PolymarketAccountSource` es el borde delgado que requiere el SDK oficial V2
(dist `polymarket-client`, import `polymarket`) + private key. Sin ellos (o si la
autenticación falla), lanza AccountUnavailableError — nunca inventa datos.
"""
from __future__ import annotations

import os
from decimal import Decimal
from typing import Protocol

from core.exceptions import AccountUnavailableError
from core.utils import to_decimal, utcnow
from portfolio.schemas.account import (
    AccountBalance,
    ClosedPositionLive,
    LivePosition,
    OpenOrder,
)

# Colateral USDC de Polymarket: entero en micro-unidades (6 decimales).
_USDC_DECIMALS = Decimal(10) ** 6


class AccountSource(Protocol):
    def get_balance(self) -> AccountBalance: ...
    def get_positions(self) -> list[LivePosition]: ...
    def get_open_orders(self) -> list[OpenOrder]: ...
    def get_closed_positions(self, limit: int = 6) -> list[ClosedPositionLive]: ...


class PolymarketAccountSource:
    """Adapter live: lee la cuenta vía el SDK oficial V2 (import `polymarket`)."""

    def __init__(self, *, private_key: str | None = None, funder: str | None = None) -> None:
        self._private_key = private_key if private_key is not None else (
            os.getenv("POLYMARKET_PRIVATE_KEY") or ""
        )
        self._funder = funder or os.getenv("POLYMARKET_FUNDER") or None
        self._client = None

    # ── conexión ──────────────────────────────────────────────────────────────

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not self._private_key:
            raise AccountUnavailableError(
                "Falta POLYMARKET_PRIVATE_KEY para leer la cuenta live."
            )
        try:
            import polymarket as pm
        except ImportError as exc:
            raise AccountUnavailableError(
                'SDK live no instalado. Corre: pip install --pre -e ".[live]"'
            ) from exc
        key = self._private_key if self._private_key.startswith("0x") else "0x" + self._private_key
        try:
            # create() deriva credenciales (handshake firmado, no mueve fondos).
            self._client = pm.SecureClient.create(private_key=key)
        except Exception as exc:  # UserInputError, RequestRejectedError, red, etc.
            raise AccountUnavailableError(
                f"No se pudo autenticar con la wallet live: {type(exc).__name__}: {exc}"
            ) from exc
        return self._client

    @property
    def wallet(self) -> str | None:
        client = self._ensure_client()
        return getattr(client, "wallet", None)

    # ── lecturas (read-only) ───────────────────────────────────────────────────

    def get_balance(self) -> AccountBalance:
        client = self._ensure_client()
        ba = client.get_balance_allowance(asset_type="COLLATERAL")
        return AccountBalance(
            usdc_balance=to_decimal(ba.balance) / _USDC_DECIMALS,
            as_of=utcnow(),
            address=getattr(client, "wallet", None),
        )

    def get_positions(self) -> list[LivePosition]:
        client = self._ensure_client()
        out: list[LivePosition] = []
        for p in client.list_positions(page_size=100).iter_items():
            out.append(LivePosition(
                condition_id=str(p.condition_id),
                token_id=str(p.token_id) if p.token_id is not None else "",
                outcome=p.outcome or "",
                size_shares=to_decimal(p.size or 0),
                avg_entry_price=to_decimal(p.avg_price or 0),
                current_price=to_decimal(p.cur_price) if p.cur_price is not None else None,
                title=p.title,
                event_id=str(p.event_id) if p.event_id is not None else None,
            ))
        return out

    def get_open_orders(self) -> list[OpenOrder]:
        client = self._ensure_client()
        out: list[OpenOrder] = []
        for o in client.list_open_orders().iter_items():
            out.append(OpenOrder(
                order_id=str(o.id),
                condition_id=str(o.market),
                token_id=str(o.token_id),
                side=o.side,
                price=to_decimal(o.price or 0),
                size_shares=to_decimal(o.original_size or 0),
                size_matched=to_decimal(o.size_matched or 0),
                status=o.status,
                created_at=o.created_at,
            ))
        return out

    def get_closed_positions(self, limit: int = 6) -> list[ClosedPositionLive]:
        client = self._ensure_client()
        out: list[ClosedPositionLive] = []
        pag = client.list_closed_positions(
            sort_by="TIMESTAMP", sort_direction="DESC", page_size=max(1, limit),
        )
        for c in pag.iter_items():
            out.append(ClosedPositionLive(
                condition_id=str(c.condition_id) if c.condition_id is not None else "",
                token_id=str(c.token_id) if c.token_id is not None else "",
                outcome=c.outcome or "",
                avg_price=to_decimal(c.avg_price or 0),
                realized_pnl=to_decimal(c.realized_pnl or 0),
                current_price=to_decimal(c.cur_price) if c.cur_price is not None else None,
                closed_at=c.timestamp,
                title=c.title,
                event_id=getattr(c, "event_slug", None),
            ))
            if len(out) >= limit:
                break
        return out
