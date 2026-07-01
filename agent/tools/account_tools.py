"""Tools de cuenta live: snapshot determinista para el agente. Inyecta AccountSource."""
from __future__ import annotations

from typing import Any

from portfolio.functions.account_reconcile import (
    index_decisions_by_condition,
    mark_to_market,
    tag_positions,
)
from portfolio.functions.account_source import AccountSource
from portfolio.schemas.account import AccountBalance, LivePosition, OpenOrder


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


def account_snapshot(source: AccountSource, *, price_of=None,
                     decisions: list[dict] | None = None) -> dict[str, Any]:
    return {
        "balance": get_balance(source),
        "positions": get_positions(source, price_of=price_of, decisions=decisions),
        "open_orders": get_open_orders(source, decisions=decisions),
    }
