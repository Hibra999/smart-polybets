"""evaluate() — aplica todas las reglas del STRATEGY.md activo y emite RiskVerdict.

Determinística: mismos inputs → mismo veredicto. Todos los thresholds vienen del
StrategyConfig (parseado del STRATEGY.md). Ningún número hardcodeado.

Lógica (orden de precedencia):
  1. DISCARD si CUALQUIER regla DISCARD aplica (aunque sea una sola).
  2. Si no, AUTO sólo si TODAS las reglas AUTO se cumplen.
  3. En cualquier otro caso → REVIEW (con las razones).

Los `qualitative_flags` (ej: QR-002 por lesión) los calcula el agente desde los
adapters y se pasan aquí; si hay alguno, fuerza REVIEW (nunca AUTO).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from core.strategy import StrategyConfig
from core.types import VerdictType
from core.utils import utcnow
from portfolio.schemas.portfolio_state import PortfolioState
from research.schemas.market_opportunity import MarketOpportunity
from risk.functions.kelly import fractional_kelly
from risk.functions.exposure import projected_exposure_pct
from risk.schemas.risk_verdict import RiskVerdict


def evaluate(
    opportunity: MarketOpportunity,
    strategy: StrategyConfig,
    portfolio_state: PortfolioState,
    *,
    qualitative_flags: list[str] | None = None,
    now: datetime | None = None,
) -> RiskVerdict:
    qualitative_flags = list(qualitative_flags or [])
    reasons: list[str] = []
    blocking: list[str] = []
    edge = opportunity.edge

    # ── Sizing (Kelly fraccional sobre el precio de mercado) ─────────────────
    kelly = fractional_kelly(
        win_probability=opportunity.model_probability,
        price=opportunity.market_probability,
        fraction_multiplier=strategy.kelly_fraction,
        bankroll_usdc=portfolio_state.bankroll_usdc,
        max_bet_usdc=strategy.max_bet_usdc,
        max_kelly_fraction=strategy.max_kelly_fraction,
    )
    size = kelly.recommended_size_usdc
    proj_exposure = projected_exposure_pct(
        portfolio_state, opportunity.participant_home, size
    )

    # ── Reglas DISCARD (cualquiera descarta) ─────────────────────────────────
    if edge < strategy.edge_threshold_discard:
        blocking.append(f"edge {edge} < discard {strategy.edge_threshold_discard}")
    if opportunity.market_volume_usdc < strategy.min_market_volume_usdc:
        blocking.append(
            f"volumen {opportunity.market_volume_usdc} < min {strategy.min_market_volume_usdc}"
        )
    if portfolio_state.drawdown_7d > strategy.max_drawdown_7d:
        blocking.append(
            f"drawdown_7d {portfolio_state.drawdown_7d} > max {strategy.max_drawdown_7d}"
        )
    if opportunity.hours_to_event < strategy.min_hours_to_event:
        blocking.append(
            f"hours_to_event {opportunity.hours_to_event} < min {strategy.min_hours_to_event}"
        )

    if blocking:
        return RiskVerdict(
            opportunity=opportunity,
            verdict=VerdictType.DISCARD,
            reasons=["DISCARD: " + "; ".join(blocking)],
            kelly_fraction=kelly.kelly_fraction,
            recommended_size_usdc=Decimal("0"),
            blocking_rules=blocking,
            qualitative_flags=qualitative_flags,
            evaluated_at=now or utcnow(),
        )

    # ── Condiciones AUTO (todas deben cumplirse) ─────────────────────────────
    auto_checks = {
        "edge>=auto": edge >= strategy.edge_threshold_auto,
        "volumen>=min": opportunity.market_volume_usdc >= strategy.min_market_volume_usdc,
        "ventana_horaria": (
            strategy.min_hours_to_event
            <= opportunity.hours_to_event
            <= strategy.max_hours_to_event
        ),
        "exposicion<max": proj_exposure < strategy.max_exposure_per_participant,
        "posiciones<max": portfolio_state.total_open_positions < strategy.max_open_positions,
        "kelly<=max": kelly.kelly_fraction <= strategy.max_kelly_fraction,
    }

    # ── Condiciones que fuerzan REVIEW ───────────────────────────────────────
    review_triggers: list[str] = []
    if strategy.edge_threshold_review <= edge < strategy.edge_threshold_auto:
        review_triggers.append(
            f"edge {edge} en zona REVIEW [{strategy.edge_threshold_review},"
            f"{strategy.edge_threshold_auto})"
        )
    if opportunity.event_phase in strategy.review_event_phases:
        review_triggers.append(f"fase {opportunity.event_phase} (mayor incertidumbre)")
    if opportunity.model_confidence == "LOW":
        review_triggers.append("model_confidence LOW")
    if qualitative_flags:
        review_triggers.append(f"flags cualitativos: {', '.join(qualitative_flags)}")
    if opportunity.hours_to_event > strategy.max_hours_to_event:
        review_triggers.append(
            f"hours_to_event {opportunity.hours_to_event} > max {strategy.max_hours_to_event}"
        )

    failed_auto = [name for name, ok in auto_checks.items() if not ok]

    if not failed_auto and not review_triggers:
        reasons.append("AUTO: todas las reglas cuantitativas satisfechas")
        verdict = VerdictType.AUTO
    else:
        verdict = VerdictType.REVIEW
        if review_triggers:
            reasons.extend(review_triggers)
        if failed_auto:
            reasons.append("no califica AUTO: " + ", ".join(failed_auto))

    return RiskVerdict(
        opportunity=opportunity,
        verdict=verdict,
        reasons=reasons,
        kelly_fraction=kelly.kelly_fraction,
        recommended_size_usdc=size,
        blocking_rules=[],
        qualitative_flags=qualitative_flags,
        evaluated_at=now or utcnow(),
    )
