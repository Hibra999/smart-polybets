"""Escaneo de mercados de Polymarket para un evento.

INTERFAZ + STUB: la fuente real de mercados es el CLOB API de Polymarket. Aquí se
define el contrato `PolymarketMarket` y `find_markets`, con una fuente inyectable
(`market_source`). El default no devuelve mercados (stub) — el wiring real provee
un callable que consulta el CLOB API.

Un PolymarketMarket describe a qué outcome del modelo corresponde el token YES,
para que edge_screener pueda comparar manzanas con manzanas.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Callable, Protocol

from pydantic import BaseModel, ConfigDict

from research.schemas.match_prediction import MatchPrediction


class PolymarketMarket(BaseModel):
    """Un mercado/outcome de Polymarket mapeado a un outcome del modelo."""

    model_config = ConfigDict(frozen=True)

    condition_id: str
    token_id: str
    outcome: str = "YES"          # token que se compra (YES/NO)
    model_outcome: str            # outcome del modelo al que resuelve YES (ej: HOME_WIN)
    market_probability: Decimal   # midpoint del token YES (0-1)
    volume_usdc: Decimal
    liquidity_usdc: Decimal

    # Campos para ejecución real en el CLOB (los llena la fuente live de Gamma;
    # opcionales para no romper las fuentes stub/snapshot).
    best_ask: Decimal | None = None       # mejor precio de venta (lo que pagás al comprar YES)
    best_bid: Decimal | None = None
    neg_risk: bool = False                # mercado neg-risk (afecta la firma de la orden)
    tick_size: Decimal | None = None      # orderPriceMinTickSize (ej: 0.001)
    min_order_size: Decimal | None = None  # orderMinSize (ej: 5)
    accepting_orders: bool = True

    # Lado NO del mismo mercado (para apuestas doble-oportunidad).
    no_token_id: str | None = None
    no_best_ask: Decimal | None = None
    no_probability: Decimal | None = None


class MarketSource(Protocol):
    def __call__(self, prediction: MatchPrediction) -> list[PolymarketMarket]: ...


def _empty_source(prediction: MatchPrediction) -> list[PolymarketMarket]:
    # Stub: sin conexión al CLOB API no hay mercados. El wiring real lo reemplaza.
    return []


def find_markets(
    prediction: MatchPrediction,
    strategy,
    *,
    market_source: Callable[[MatchPrediction], list[PolymarketMarket]] | None = None,
) -> list[PolymarketMarket]:
    """Mercados de Polymarket para el evento, filtrados por volumen mínimo.

    El filtro de liquidez se aplica acá: NUNCA se devuelve un mercado con volumen
    por debajo de `min_market_volume_usdc` del STRATEGY.md (mercado ilíquido).
    """
    source = market_source or _empty_source
    markets = source(prediction)
    min_vol = getattr(strategy, "min_market_volume_usdc", Decimal("0"))
    return [m for m in markets if m.volume_usdc >= min_vol]
