"""MarketOpportunity — output de research, input de optimization y risk.

Agnóstico al deporte. Es el contrato central del pipeline.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from core.utils import date_str, make_idempotency_key


class MarketOpportunity(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Identificadores de Polymarket
    polymarket_condition_id: str
    polymarket_token_id: str
    outcome: str  # "YES" | "NO"
    model_outcome: str | None = None  # lado del modelo que resuelve YES (HOME_WIN/AWAY_WIN);
    #                                   opcional para no romper fuentes/registros previos

    # Identificadores del evento deportivo (genéricos)
    tournament_id: str
    sport: str
    event_id: str
    market_type: str
    strategy_id: str

    # Probabilidades
    model_probability: Decimal  # 0.0 - 1.0
    market_probability: Decimal  # 0.0 - 1.0
    edge: Decimal  # model_probability - market_probability

    # Contexto del evento (genérico)
    participant_home: str
    participant_away: str
    event_start_utc: datetime
    hours_to_event: float
    event_phase: str  # "group" | "playoff" | "final" | "regular_season"

    # Contexto del mercado Polymarket
    market_volume_usdc: Decimal
    market_liquidity_usdc: Decimal
    question: str | None = None
    rules: str | None = None

    # Metadata del modelo
    model_version: str
    model_confidence: str  # "HIGH" | "MEDIUM" | "LOW"
    sample_size: int

    # Metadata de ejecución real (se propaga desde el PolymarketMarket live para
    # poder firmar la orden). Opcional: las fuentes stub/snapshot no la traen.
    best_ask: Decimal | None = None        # precio de compra real del token YES
    neg_risk: bool = False
    tick_size: Decimal | None = None
    min_order_size: Decimal | None = None
    best_ask_size: Decimal | None = None
    ask_levels: tuple[tuple[Decimal, Decimal], ...] = ()
    fee_rate_bps: int | None = None

    # Timestamp y versión para idempotencia y auditoría
    generated_at: datetime
    strategy_version: str

    @field_validator("edge")
    @classmethod
    def edge_must_be_in_range(cls, v: Decimal) -> Decimal:
        if not (-1 <= v <= 1):
            raise ValueError("Edge fuera de rango")
        return v

    @property
    def idempotency_key(self) -> str:
        """Clave determinística de la oportunidad (ver core.utils.make_idempotency_key)."""
        return make_idempotency_key(
            self.polymarket_condition_id,
            self.outcome,
            self.strategy_id,
            self.strategy_version,
            date_str(self.generated_at),
        )
