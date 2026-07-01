"""Envío de la orden al CLOB de Polymarket — delega en PolymarketBroker.

Por defecto el broker corre en DRY-RUN (no toca la red ni la wallet) y devuelve un
OrderResult `status="dry_run"`. Para ejecución real se inyecta un broker con
`live=True` (que además exige credenciales + POLYMARKET_LIVE=1). Ver broker.py.

NUNCA debe llamarse si ExecutionDecision.requires_approval == True (eso lo
garantiza el agente/workflow vía execution_tools.submit).
"""
from __future__ import annotations

from execution.functions.broker import PolymarketBroker
from execution.schemas.order_result import OrderResult
from execution.schemas.trade_order import TradeOrder


def submit_order(order: TradeOrder, *, broker: PolymarketBroker | None = None) -> OrderResult:
    return (broker or PolymarketBroker(live=False)).place(order)
