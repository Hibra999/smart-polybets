"""Tools de Portfolio para el agente. Construye el LocalStateClient si no se inyecta."""
from __future__ import annotations

from typing import Any

from core.local_state import LocalStateClient
from execution.schemas.execution_decision import ExecutionDecision
from execution.schemas.order_result import OrderResult
from portfolio.functions import position_tracker
from portfolio.functions.performance_metrics import summary
from portfolio.schemas.performance_summary import PerformanceSummary
from portfolio.schemas.portfolio_state import PortfolioState


def _client(client: LocalStateClient | None) -> LocalStateClient:
    return client or LocalStateClient()


def get_state(client: LocalStateClient | None = None) -> PortfolioState:
    return position_tracker.get_state(_client(client))


def check_idempotency(idempotency_key: str, client: LocalStateClient | None = None) -> dict | None:
    return position_tracker.check_idempotency(_client(client), idempotency_key)


def save_decision(decision: ExecutionDecision, client: LocalStateClient | None = None) -> dict:
    return position_tracker.save_decision(_client(client), decision)


def mark_executed(
    idempotency_key: str, order_result: OrderResult, client: LocalStateClient | None = None
) -> dict:
    return position_tracker.mark_executed(_client(client), idempotency_key, order_result)


def mark_simulated(
    idempotency_key: str, order_result: OrderResult, client: LocalStateClient | None = None
) -> dict:
    return position_tracker.mark_simulated(_client(client), idempotency_key, order_result)


def performance_summary(
    portfolio_state: PortfolioState,
    resolved_trades: list[dict[str, Any]] | None = None,
    *,
    tournament_id: str | None = None,
) -> PerformanceSummary:
    return summary(portfolio_state, resolved_trades, tournament_id=tournament_id)
