"""Cálculo de edge → construcción de MarketOpportunity. Función pura."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from core.strategy import StrategyConfig
from core.utils import hours_between, utcnow
from research.functions.market_scanner import PolymarketMarket
from research.functions.probability_extractor import get_model_prob
from research.schemas.match_prediction import MatchPrediction
from research.schemas.market_opportunity import MarketOpportunity


def calculate_edge(
    prediction: MatchPrediction,
    market: PolymarketMarket,
    strategy: StrategyConfig,
    *,
    now: datetime | None = None,
    model_probability: Decimal | None = None,
) -> MarketOpportunity | None:
    """Construye una MarketOpportunity con edge = p_modelo - p_polymarket.

    `model_probability` permite forzar la prob del modelo (ej: la prob TrueSkill
    del lado elegido por la estrategia). Si es None, se toma del outcome
    del mercado en la predicción (camino genérico). Retorna None si no hay prob.
    """
    model_prob = (
        model_probability if model_probability is not None
        else get_model_prob(prediction, market.model_outcome)
    )
    if model_prob is None:
        return None

    edge = model_prob - market.market_probability
    ref = now or utcnow()

    return MarketOpportunity(
        polymarket_condition_id=market.condition_id,
        polymarket_token_id=market.token_id,
        outcome=market.outcome,
        model_outcome=market.model_outcome,
        tournament_id=prediction.tournament_id,
        sport=prediction.sport,
        event_id=prediction.event_id,
        market_type=prediction.market_type,
        strategy_id=strategy.strategy_id or strategy.market_type,
        model_probability=model_prob,
        market_probability=market.market_probability,
        edge=edge,
        participant_home=prediction.participant_home,
        participant_away=prediction.participant_away,
        event_start_utc=prediction.event_start_utc,
        hours_to_event=hours_between(ref, prediction.event_start_utc),
        event_phase=prediction.event_phase,
        market_volume_usdc=market.volume_usdc,
        market_liquidity_usdc=market.liquidity_usdc,
        best_ask=market.best_ask,
        neg_risk=market.neg_risk,
        tick_size=market.tick_size,
        min_order_size=market.min_order_size,
        model_version=prediction.model_version,
        model_confidence=prediction.model_confidence.value,
        sample_size=prediction.sample_size,
        generated_at=ref,
        strategy_version=strategy.version,
    )
