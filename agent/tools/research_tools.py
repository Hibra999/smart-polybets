"""Tools de Research para el agente."""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from core.strategy import StrategyConfig
from research.functions import calculate_edge, find_markets, get_event_prediction
from research.functions.market_scanner import PolymarketMarket
from research.functions.strategy_selection import build_strategy_opportunity
from research.schemas.market_opportunity import MarketOpportunity
from research.schemas.match_prediction import MatchPrediction


def event_prediction(event_id: str, tournament_id: str) -> MatchPrediction | None:
    return get_event_prediction(event_id, tournament_id)


def markets_for(prediction: MatchPrediction, strategy: StrategyConfig,
                market_source: Callable | None = None) -> list[PolymarketMarket]:
    return find_markets(prediction, strategy, market_source=market_source)


def scan_event(
    event_id: str,
    tournament_id: str,
    strategy: StrategyConfig,
    *,
    market_source: Callable | None = None,
    now: datetime | None = None,
) -> list[MarketOpportunity]:
    """Pipeline de research para un evento: predicción → mercados → oportunidades.

    Si la predicción trae componentes por modelo, aplica la
    estrategia de selección de lado migrada (`build_strategy_opportunity`): elige
    UN lado según `side_criterion` y respeta warmup + filtro Bayes. Si no, usa el
    camino genérico (una oportunidad por mercado).
    """
    prediction = get_event_prediction(event_id, tournament_id)
    if prediction is None:
        return []
    markets = find_markets(prediction, strategy, market_source=market_source)

    if prediction.components:
        from research.functions.poisson_loader import match_result_probs
        poisson_result = (match_result_probs(strategy.tournament_id, prediction.event_id)
                          if strategy.bet_type == "double_chance" else None)
        opp = build_strategy_opportunity(prediction, markets, strategy, now=now,
                                         poisson_result=poisson_result)
        return [opp] if opp is not None else []

    opps = [calculate_edge(prediction, m, strategy, now=now) for m in markets]
    return [o for o in opps if o is not None]
