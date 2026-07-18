"""Tools de cuenta live: snapshot determinista para el agente. Inyecta AccountSource."""
from __future__ import annotations

from typing import Any

from decimal import Decimal

from portfolio.functions.account_reconcile import (
    index_decisions_by_condition,
    mark_to_market,
    tag_positions,
)
from portfolio.functions.account_source import AccountSource
from portfolio.functions.pnl import realized_pnl_cashflow
from portfolio.schemas.account import (
    AccountBalance,
    ClosedPositionLive,
    LivePosition,
    LiveRedemption,
    LiveTrade,
    OpenOrder,
)


def get_balance(source: AccountSource) -> AccountBalance:
    return source.get_balance()


def get_positions(source: AccountSource, *, price_of=None,
                  decisions: list[dict] | None = None) -> list[LivePosition]:
    positions = source.get_positions()
    if decisions:
        positions = tag_positions(positions, decisions)
    if price_of is not None:
        positions = mark_to_market(positions, price_of)
    return positions


def get_open_orders(source: AccountSource, *,
                    decisions: list[dict] | None = None) -> list[OpenOrder]:
    orders = source.get_open_orders()
    if not decisions:
        return orders
    idx = index_decisions_by_condition(decisions)
    out: list[OpenOrder] = []
    for o in orders:
        d = idx.get(o.condition_id)
        if d is None:
            out.append(o)
            continue
        opp = d.get("opportunity_json") or {}
        out.append(o.model_copy(update={
            "event_id": opp.get("event_id"),
            "tournament_id": d.get("tournament_id"),
            "strategy_id": d.get("strategy_id"),
        }))
    return out


def get_closed_positions(source: AccountSource, *, limit: int = 6) -> list[ClosedPositionLive]:
    return source.get_closed_positions(limit=limit)


def get_trades(source: AccountSource) -> list[LiveTrade]:
    fn = getattr(source, "get_trades", None)
    return list(fn()) if fn is not None else []


def get_redemptions(source: AccountSource) -> list[LiveRedemption]:
    fn = getattr(source, "get_redemptions", None)
    return list(fn()) if fn is not None else []


def get_realized_pnl(source: AccountSource) -> Decimal | None:
    """PnL realizado por FLUJO DE CAJA (Σ ventas + Σ redenciones − Σ compras).

    Es el método que cuadra con la UI de Polymarket. None si la fuente no expone
    trades (fuentes viejas/fakes) → el caller cae al método de snapshot.
    """
    if getattr(source, "get_trades", None) is None:
        return None
    return realized_pnl_cashflow(get_trades(source), get_redemptions(source))


def account_snapshot(source: AccountSource, *, price_of=None,
                     decisions: list[dict] | None = None,
                     closed_limit: int = 6) -> dict[str, Any]:
    return {
        "balance": get_balance(source),
        "positions": get_positions(source, price_of=price_of, decisions=decisions),
        "open_orders": get_open_orders(source, decisions=decisions),
        "closed": get_closed_positions(source, limit=closed_limit),
        "trades": get_trades(source),
        "redemptions": get_redemptions(source),
        "realized_pnl": get_realized_pnl(source),  # cash-flow; None si no disponible
    }
