"""Tools del carril CIO-override: apuestas manuales QUE PASAN por el pipeline.

Una apuesta que ninguna estrategia genera (lado Poisson, totales, sizing del CIO)
se propone acá como Decision real: riesgo la evalúa con los límites de la estrategia
activa, el verdict se fuerza a REVIEW (un override NUNCA es AUTO) y queda en el
ledger (`LocalState`) con la idempotency key estándar. La colocación es la ruta
confiable existente: `orders.py --approve <key> --live --confirm <monto>`.

El flujo obliga a pasar por riesgo, REVIEW e idempotencia.
"""
from __future__ import annotations

from decimal import Decimal

from core.local_state import LocalStateClient
from core.strategy import StrategyConfig
from core.types import VerdictType
from core.utils import utcnow
from execution.functions import classify
from execution.functions.order_builder import build_order
from portfolio.functions import position_tracker
from research.schemas.market_opportunity import MarketOpportunity
from risk.functions import evaluate as risk_evaluate
from risk.schemas.risk_verdict import RiskVerdict

OVERRIDE_STRATEGY_ID = "cio_override"
OVERRIDE_STRATEGY_VERSION = "1.0"


def propose_override(
    opportunity: MarketOpportunity,
    *,
    stake_usdc: Decimal,
    reason: str,
    client: LocalStateClient,
    strategy: StrategyConfig,
    qualitative_flags: list[str] | None = None,
) -> dict:
    """Propone una apuesta manual como Decision REVIEW en el ledger.

    Devuelve {"mode": "REVIEW"|"DISCARD"|"SKIP", ...}. Solo REVIEW persiste.
    El motor de riesgo puede DISCARDear (edge < umbral, volumen, drawdown,
    proximidad al evento, exposure): ese es el control que la ruta manual vieja
    no tenía. El stake es el del CIO, no el Kelly de la estrategia.
    """
    if not reason or not reason.strip():
        raise ValueError("un override requiere --reason (queda en el ledger)")
    if stake_usdc <= 0:
        raise ValueError("stake_usdc debe ser > 0")

    key = opportunity.idempotency_key

    # 1. Idempotencia — obligatoria antes de procesar (regla de oro #4).
    existing = position_tracker.check_idempotency(client, key)
    if existing is not None and existing.get("status") not in ("expired", "simulated"):
        return {"mode": "SKIP", "idempotency_key": key,
                "reason": f"ya procesada (status={existing.get('status')})"}

    # 2. Riesgo con los límites de la estrategia activa.
    state = position_tracker.get_state(client)
    verdict = risk_evaluate(opportunity, strategy, state,
                            qualitative_flags=qualitative_flags)
    if verdict.verdict == VerdictType.DISCARD:
        return {"mode": "DISCARD", "idempotency_key": key,
                "reasons": verdict.reasons, "blocking_rules": verdict.blocking_rules}

    # 3. Forzar REVIEW con el stake del CIO (nunca AUTO: siempre aprobación tipeada).
    forced = RiskVerdict(
        opportunity=opportunity,
        verdict=VerdictType.REVIEW,
        reasons=[*verdict.reasons, f"CIO override: {reason.strip()}"],
        kelly_fraction=verdict.kelly_fraction,
        recommended_size_usdc=stake_usdc,
        blocking_rules=verdict.blocking_rules,
        qualitative_flags=verdict.qualitative_flags,
        evaluated_at=utcnow(),
    )

    # 4. Decision + persistencia (status pending_approval).
    order = build_order(forced)
    decision = classify(order, forced)
    saved = position_tracker.save_decision(client, decision)
    return {"mode": "REVIEW", "idempotency_key": key, "saved": saved,
            "recommended_size": str(stake_usdc)}
