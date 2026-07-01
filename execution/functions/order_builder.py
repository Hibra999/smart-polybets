"""Construcción del payload de orden para el CLOB API. Función pura."""
from __future__ import annotations

from decimal import Decimal

from core.types import OrderSide, OrderType
from core.utils import quantize_usdc, to_decimal
from execution.schemas.trade_order import TradeOrder
from optimization.schemas.sizing_output import SizingOutput
from research.functions.market_scanner import PolymarketMarket
from risk.schemas.risk_verdict import RiskVerdict


def build(
    verdict: RiskVerdict,
    sizing: SizingOutput,
    live_price: Decimal | float,
    *,
    order_type: OrderType = OrderType.LIMIT,
    side: OrderSide = OrderSide.BUY,
    market: PolymarketMarket | None = None,
) -> TradeOrder:
    """Construye un TradeOrder con el precio LIVE (no el de la señal).

    Si se pasa `market` (de la fuente live de Gamma), copia los datos de ejecución
    real: token_id/condition_id reales, neg_risk, tick_size y min_order_size.
    """
    opp = verdict.opportunity
    price = to_decimal(live_price)
    size = sizing.size_usdc
    shares = (size / price) if price > 0 else Decimal("0")

    condition_id = opp.polymarket_condition_id
    token_id = opp.polymarket_token_id
    # Metadata de ejecución: del market si se pasa, si no de la propia oportunidad
    # (que ya la trae propagada desde la fuente live).
    if market is not None:
        condition_id = market.condition_id
        token_id = market.token_id
        neg_risk = market.neg_risk
        tick_size = market.tick_size
        min_order_size = market.min_order_size
    else:
        neg_risk = opp.neg_risk
        tick_size = opp.tick_size
        min_order_size = opp.min_order_size

    return TradeOrder(
        condition_id=condition_id,
        token_id=token_id,
        outcome=opp.outcome,
        side=side,
        order_type=order_type,
        price=price,
        size_usdc=quantize_usdc(size),
        size_shares=Decimal(str(round(float(shares), 4))),
        neg_risk=neg_risk,
        tick_size=tick_size,
        min_order_size=min_order_size,
    )


def build_order(
    verdict: RiskVerdict,
    sizing: SizingOutput | None = None,
    live_price: Decimal | float | None = None,
    **kwargs,
) -> TradeOrder:
    """Conveniencia: construye la orden desde el verdict.

    Si no se pasa `sizing`, usa el tamaño recomendado del verdict. Si no se pasa
    `live_price`, usa el precio de la señal (market_probability) — válido para el
    camino AUTO donde el precio no se movió.
    """
    opp = verdict.opportunity
    if sizing is None:
        sizing = SizingOutput(
            size_usdc=verdict.recommended_size_usdc,
            method="from_verdict",
            kelly_fraction=verdict.kelly_fraction,
        )
    if live_price is None:
        # Para comprar YES se paga el best_ask (precio real); si no hay, el midpoint.
        live_price = opp.best_ask if opp.best_ask is not None else opp.market_probability
    return build(verdict, sizing, live_price, **kwargs)
