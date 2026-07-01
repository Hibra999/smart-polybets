"""Optimización de un batch de oportunidades (cvxpy con fallback).

Maximiza el EV esperado del batch (sum edge_i * x_i) sujeto a:
  - presupuesto total <= bankroll disponible
  - x_i <= max_bet_usdc
  - x_i >= 0

cvxpy es OPCIONAL. Si no está instalado o no converge, se degrada a asignar el
tamaño que ya recomendó cada RiskVerdict (capado a max_bet) — Kelly fraccional
simple como fallback, tal como pide el whitepaper.
"""
from __future__ import annotations

from decimal import Decimal

from core.strategy import StrategyConfig
from core.utils import quantize_usdc
from optimization.schemas.optimization_result import OptimizationResult
from optimization.schemas.sizing_output import SizingOutput
from portfolio.schemas.portfolio_state import PortfolioState
from risk.schemas.risk_verdict import RiskVerdict


def _fallback(verdicts: list[RiskVerdict], strategy: StrategyConfig,
              note: str) -> OptimizationResult:
    allocations: dict[str, SizingOutput] = {}
    for v in verdicts:
        size = min(v.recommended_size_usdc, strategy.max_bet_usdc)
        skipped = size < strategy.min_bet_usdc
        allocations[v.opportunity.idempotency_key] = SizingOutput(
            size_usdc=Decimal("0") if skipped else quantize_usdc(size),
            method="fallback_kelly",
            kelly_fraction=v.kelly_fraction,
            skipped=skipped,
            notes=[note] if note else [],
        )
    return OptimizationResult(
        allocations=allocations, converged=False, method="fallback_kelly",
        notes=[note] if note else [],
    )


def optimize_batch(
    verdicts: list[RiskVerdict],
    portfolio_state: PortfolioState,
    strategy: StrategyConfig,
    *,
    budget_fraction: Decimal = Decimal("0.5"),
) -> OptimizationResult:
    """Asigna capital al batch maximizando EV. budget_fraction = % del bankroll
    disponible para este batch."""
    actionable = [v for v in verdicts if v.recommended_size_usdc > 0]
    if not actionable:
        return OptimizationResult(allocations={}, converged=True, method="empty")

    try:
        import cvxpy as cp  # type: ignore
    except ImportError:
        return _fallback(actionable, strategy, "cvxpy no instalado")

    import numpy as np

    n = len(actionable)
    edges = np.array([float(v.opportunity.edge) for v in actionable])
    max_bet = float(strategy.max_bet_usdc)
    budget = float(portfolio_state.bankroll_usdc) * float(budget_fraction)

    x = cp.Variable(n, nonneg=True)
    objective = cp.Maximize(edges @ x)
    constraints = [cp.sum(x) <= budget, x <= max_bet]
    prob = cp.Problem(objective, constraints)
    try:
        prob.solve()
    except Exception as exc:  # pragma: no cover - depende del solver
        return _fallback(actionable, strategy, f"cvxpy falló: {exc}")

    if x.value is None or prob.status not in {"optimal", "optimal_inaccurate"}:
        return _fallback(actionable, strategy, f"cvxpy no convergió ({prob.status})")

    allocations: dict[str, SizingOutput] = {}
    for v, xi in zip(actionable, x.value):
        size = Decimal(str(round(float(xi), 2)))
        skipped = size < strategy.min_bet_usdc
        allocations[v.opportunity.idempotency_key] = SizingOutput(
            size_usdc=Decimal("0") if skipped else size,
            method="cvxpy_batch",
            kelly_fraction=v.kelly_fraction,
            skipped=skipped,
        )
    return OptimizationResult(
        allocations=allocations,
        objective_value=Decimal(str(round(float(prob.value), 4))),
        converged=True,
        method="cvxpy_batch",
    )
