"""Tools de Execution para el agente.

`submit` GUARDA contra el error más costoso del sistema: nunca envía una orden si
el ExecutionDecision requiere aprobación.
"""
from __future__ import annotations

from decimal import Decimal

from core.exceptions import AgentError
from execution.functions import (
    PolymarketBroker,
    classify,
    submit_order,
    validate_live_price,
)
from execution.functions.order_builder import build_order as _build_order
from execution.schemas.execution_decision import ExecutionDecision
from execution.schemas.order_result import OrderResult
from execution.schemas.trade_order import TradeOrder
from optimization.schemas.sizing_output import SizingOutput
from research.functions.market_scanner import PolymarketMarket
from risk.schemas.risk_verdict import RiskVerdict


def build_order(verdict: RiskVerdict, sizing: SizingOutput | None = None,
                live_price: Decimal | float | None = None,
                *, market: PolymarketMarket | None = None) -> TradeOrder:
    """Construye la orden. Sin `live_price` usa best_ask de la oportunidad (compra real)."""
    return _build_order(verdict, sizing, live_price, market=market)


def classify_order(order: TradeOrder, verdict: RiskVerdict) -> ExecutionDecision:
    return classify(order, verdict)


def validate_price(signal_price, live_price, tolerance=Decimal("0.02")) -> bool:
    return validate_live_price(signal_price, live_price, tolerance)


def submit(order: TradeOrder, decision: ExecutionDecision,
           *, broker: PolymarketBroker | None = None) -> OrderResult:
    """Envía la orden SÓLO si no requiere aprobación. Caso contrario, levanta.

    `broker` permite inyectar un broker live; por defecto es dry-run.
    """
    if decision.requires_approval:
        raise AgentError(
            f"submit bloqueado: {decision.idempotency_key} requiere aprobación humana (REVIEW)"
        )
    return submit_order(order, broker=broker)
