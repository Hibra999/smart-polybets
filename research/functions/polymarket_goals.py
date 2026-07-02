"""Fuente de mercados de GOLES (Over/Under, BTTS) — pendiente de migración al gateway.

Task 1.3: se retiró el scraper Gamma (HTTP directo). La función `fetch_goals_market`
devuelve `None` temporalmente hasta que el gateway soporte descubrimiento de mercados
de goles. El contrato (`GoalsMarket`, `fetch_goals_market`) se preserva para no romper
los imports existentes (`scripts/place_over.py`).

TODO Task 2.x: implementar `PolymarketGateway.find_goals_markets(home, away, ...)`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from research.functions.polymarket_live import _canon  # noqa: F401 — re-export compat

WORLD_CUP_TAG_ID = 102232
_MORE = re.compile(r"^(.+?)\s+vs\.?\s+(.+?)\s*-\s*More\s+Markets", re.I)


@dataclass(frozen=True)
class GoalsMarket:
    question: str
    outcome_label: str          # "Over" | "Under" | "Yes" | "No"
    token_id: str
    condition_id: str
    price: Decimal              # mid (outcomePrices del outcome elegido)
    best_ask: Decimal | None
    neg_risk: bool
    tick_size: Decimal | None
    min_order_size: Decimal | None
    accepting_orders: bool


def fetch_goals_market(
    home: str,
    away: str,
    *,
    kind: str = "ou",
    line: float = 2.5,
    outcome: str = "Over",
    tag_id: int = WORLD_CUP_TAG_ID,
    timeout: int = 20,
    session=None,
) -> GoalsMarket | None:
    """Pendiente: migrar al gateway SDK (sin scraper Gamma).

    Devuelve None hasta que `PolymarketGateway.find_goals_markets` esté implementado.
    """
    return None
