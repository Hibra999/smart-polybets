"""Broker de Polymarket — delega en PolymarketGateway (SDK oficial CLOB V2).

Reimplementado en Task 1.3: delega en `PolymarketGateway` en lugar de duplicar la
lógica de ejecución. El contrato público (clase, constructores, `round_to_tick`,
`OrderResult` shapes/statuses, gates de seguridad) se preserva íntegro.
"""
from __future__ import annotations

from decimal import Decimal

from execution.schemas.order_result import OrderResult
from execution.schemas.trade_order import TradeOrder
from venue.gateway import PolymarketGateway, round_to_tick  # noqa: F401 — re-export


class PolymarketBroker:
    """Envía órdenes al CLOB V2 de Polymarket (o simula en dry-run)."""

    def __init__(
        self,
        *,
        live: bool = False,
        private_key: str | None = None,
        funder: str | None = None,
    ) -> None:
        self._gateway = PolymarketGateway(live=live, private_key=private_key, funder=funder)
        # Expor atributos que los tests comprueban directamente
        self.live = self._gateway.live
        self.private_key = self._gateway.private_key
        self.funder = self._gateway.funder
        self._blocked_reason = self._gateway._blocked_reason

    def place(self, order: TradeOrder) -> OrderResult:
        return self._gateway.place(order)

    def cancel(self, order_id: str) -> OrderResult:
        return self._gateway.cancel(order_id)

    def best_ask(self, token_id: str) -> Decimal | None:
        return self._gateway.best_ask(token_id)
