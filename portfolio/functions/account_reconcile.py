"""Lógica pura de cuenta: indexado, mark-to-market, tagging y reconciliación.

Sin red ni SDK: recibe posiciones/orders (de un AccountSource) y las decisiones del
estado local. La escritura (ajuste de bankroll) la hace el script bajo --reconcile.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from core.utils import to_decimal
from portfolio.schemas.account import AccountBalance, LivePosition

PriceOf = Callable[[LivePosition], "Decimal | None"]


def _condition_of(decision: dict) -> str | None:
    return decision.get("condition_id") or (
        decision.get("opportunity_json") or {}
    ).get("polymarket_condition_id")


def index_decisions_by_condition(decisions: list[dict]) -> dict[str, dict]:
    """{condition_id -> primera decisión con ese condition_id}."""
    idx: dict[str, dict] = {}
    for d in decisions:
        cid = _condition_of(d)
        if cid:
            idx.setdefault(cid, d)
    return idx


def mark_to_market(positions: list[LivePosition], price_of: PriceOf) -> list[LivePosition]:
    """Devuelve copias con current_price poblado (best_bid live); unrealized_pnl deriva."""
    out: list[LivePosition] = []
    for p in positions:
        price = price_of(p)
        out.append(p.model_copy(update={"current_price": price})
                   if price is not None else p)
    return out


def tag_positions(positions: list[LivePosition], decisions: list[dict]) -> list[LivePosition]:
    """Etiqueta event/tournament/strategy por condition_id; deja None si no mapea."""
    idx = index_decisions_by_condition(decisions)
    out: list[LivePosition] = []
    for p in positions:
        d = idx.get(p.condition_id)
        if d is None:
            out.append(p)
            continue
        opp = d.get("opportunity_json") or {}
        out.append(p.model_copy(update={
            "event_id": opp.get("event_id"),
            "tournament_id": d.get("tournament_id"),
            "strategy_id": d.get("strategy_id"),
        }))
    return out


def reconcile(
    decisions: list[dict],
    balance: AccountBalance,
    positions: list[LivePosition],
    *,
    bankroll_param: Decimal | float,
) -> dict[str, Any]:
    """Compara realidad on-chain vs ledger local → reporte de drift (no escribe)."""
    bankroll_param = to_decimal(bankroll_param)
    live_cids = {p.condition_id for p in positions}
    executed = [d for d in decisions if d.get("status") == "executed"]
    exec_cids = {_condition_of(d) for d in executed}
    exec_cids.discard(None)

    return {
        "bankroll_param": bankroll_param,
        "balance_real": balance.usdc_balance,
        "bankroll_delta": balance.usdc_balance - bankroll_param,
        "n_live_positions": len(positions),
        "n_executed_local": len(executed),
        "missing_fills": sorted(exec_cids - live_cids),
        "external_positions": sorted(live_cids - exec_cids),
        "as_of": balance.as_of.isoformat(),
    }
