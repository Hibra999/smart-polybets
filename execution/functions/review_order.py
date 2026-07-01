"""Aprobación de una decisión REVIEW → TradeOrder. Funciones puras (sin red).

`validate_placeable` decide si una decisión guardada se puede colocar AHORA
(evento no empezado, token válido, precio live sano, slippage dentro de tolerancia).
`build_trade_order_from_decision` arma el TradeOrder al precio live (nunca al de la
señal guardada).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from core.types import OrderSide, OrderType
from core.utils import to_decimal
from execution.functions.price_validator import validate_live_price
from execution.schemas.trade_order import TradeOrder


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def validate_placeable(
    decision: dict,
    *,
    now: datetime,
    live_price: Decimal | None,
    tolerance: Decimal = Decimal("0.15"),
) -> tuple[bool, str]:
    opp = decision.get("opportunity_json") or {}
    token = opp.get("polymarket_token_id")
    if not token:
        return False, "sin token_id en la decisión"
    start = opp.get("event_start_utc")
    if start and _parse_utc(start) <= now:
        return False, "el evento ya empezó/terminó"
    if live_price is None or to_decimal(live_price) <= 0:
        return False, "no se pudo repreciar (best_ask live no disponible)"
    signal = opp.get("best_ask") or opp.get("market_probability")
    if signal is None:
        return False, "sin precio de señal para comparar slippage"
    if not validate_live_price(signal, live_price, tolerance):
        return False, f"slippage: live {live_price} vs señal {signal} > {tolerance}"
    return True, "ok"


def build_trade_order_from_decision(decision: dict, live_price: Decimal) -> TradeOrder:
    opp = decision.get("opportunity_json") or {}
    price = to_decimal(live_price)
    size_usdc = to_decimal(decision.get("recommended_size", 0))
    shares = (size_usdc / price) if price > 0 else Decimal("0")
    tick = opp.get("tick_size")
    minsz = opp.get("min_order_size")
    return TradeOrder(
        condition_id=opp.get("polymarket_condition_id") or decision.get("condition_id", ""),
        token_id=str(opp.get("polymarket_token_id", "")),
        outcome=opp.get("outcome", "YES"),
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=price,
        size_usdc=size_usdc,
        size_shares=shares,
        neg_risk=bool(opp.get("neg_risk", False)),
        tick_size=to_decimal(tick) if tick is not None else None,
        min_order_size=to_decimal(minsz) if minsz is not None else None,
    )
