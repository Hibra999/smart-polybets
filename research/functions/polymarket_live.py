"""Fuente de mercados LIVE de Polymarket (read-only) — ahora vía el gateway oficial.

Reimplementado en Task 1.3: delega en `PolymarketGateway.find_match_markets` en lugar
del scraper hand-rolled al Gamma API. El contrato público (clase, constructores, Protocol
`MarketSource`) se preserva íntegro.

La lógica de matching/canonicalización vive ahora en `venue.matching`.
"""
from __future__ import annotations

from venue.matching import canon as _canon  # re-export para compat con scripts externos

from research.functions.market_scanner import PolymarketMarket
from research.schemas.match_prediction import MatchPrediction

# PolymarketGateway se importa lazy (dentro de __call__) para evitar el ciclo:
#   broker → venue.gateway → research.functions.market_scanner
#   → research.functions.__init__ → polymarket_live → venue.gateway

WORLD_CUP_TAG_ID = 102232


class PolymarketLiveSource:
    """market_source que consulta Polymarket en vivo vía el gateway SDK (read-only)."""

    def __init__(
        self,
        *,
        tag_id: int = WORLD_CUP_TAG_ID,
        accepting_only: bool = True,
        # Parámetros legacy (ignorados; se conservan para compatibilidad con código
        # existente que los pase positionally-or-by-name).
        max_events: int = 800,
        timeout: int = 20,
        session=None,
    ) -> None:
        self.tag_id = tag_id
        self.accepting_only = accepting_only

    def refresh(self) -> None:
        """No-op: el gateway siempre trae datos frescos del SDK."""

    # ── market_source API ────────────────────────────────────────────────────

    def __call__(self, prediction: MatchPrediction) -> list[PolymarketMarket]:
        from venue.gateway import PolymarketGateway  # lazy — evita ciclo de importación
        gw = PolymarketGateway()
        markets = gw.find_match_markets(
            prediction.participant_home,
            prediction.participant_away,
            tag_ids=self.tag_id,
        )
        if self.accepting_only:
            markets = [m for m in markets if m.accepting_orders]
        return markets
