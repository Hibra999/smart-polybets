"""Fuente de mercados LIVE de Polymarket (read-only) — ahora vía el gateway oficial.

Reimplementado en Task 1.3: delega en `PolymarketGateway.find_match_markets` en lugar
del scraper hand-rolled al Gamma API. El contrato público (clase, constructores, Protocol
`MarketSource`) se preserva íntegro.

La lógica de matching/canonicalización vive ahora en `venue.matching`.
"""
from __future__ import annotations

from research.functions.market_scanner import PolymarketMarket
from research.schemas.match_prediction import MatchPrediction

# PolymarketGateway se importa lazy (dentro de __call__) como defensa: hoy NO hay ciclo
# real (a nivel de módulo sólo se importa venue.matching), pero el import diferido evita
# uno si en el futuro se agrega un import top-level de venue.gateway en este archivo.

class PolymarketLiveSource:
    """market_source que consulta Polymarket en vivo vía el gateway SDK (read-only)."""

    def __init__(
        self,
        *,
        tag_id: int,
        accepting_only: bool = True,
        # Parámetros legacy (ignorados; se conservan para compatibilidad con código
        # existente que los pase positionally-or-by-name).
        max_events: int = 800,
        timeout: int = 20,
        session=None,
    ) -> None:
        self.tag_id = tag_id
        self.accepting_only = accepting_only
        self._gateway = None  # PolymarketGateway cacheado (init lazy en __call__)

    def refresh(self) -> None:
        """No-op: el gateway siempre trae datos frescos del SDK."""

    # ── market_source API ────────────────────────────────────────────────────

    def __call__(self, prediction: MatchPrediction) -> list[PolymarketMarket]:
        if self._gateway is None:
            from venue.gateway import PolymarketGateway  # lazy import (defensivo)
            self._gateway = PolymarketGateway()
        markets = self._gateway.find_match_markets(
            prediction.participant_home,
            prediction.participant_away,
            tag_ids=self.tag_id,
        )
        if self.accepting_only:
            markets = [m for m in markets if m.accepting_orders]
        return markets
