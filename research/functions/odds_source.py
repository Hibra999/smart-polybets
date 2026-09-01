"""Fuente de mercados desde cuotas históricas guardadas en SQLite.

`SqliteOddsSource` es un `market_source` para `research.find_markets` /
`research_tools.scan_event`: dado un MatchPrediction, busca las cuotas del fixture
en la tabla `polymarket_odds` del SQLite del torneo y las convierte en
PolymarketMarket por lado
("Will home win" / "Will away win").

Las cuotas migradas traen la probabilidad implícita (home_prob/away_prob = 1/cuota
decimal) pero NO volumen ni los condition_id/token_id reales de Polymarket. Por eso:
  - market_probability = home_prob / away_prob (el midpoint del token YES).
  - volume/liquidity = placeholders configurables (el dato real vendrá del CLOB API).
  - condition_id/token_id = sintéticos determinísticos (f"{fixture}:HOME").

Cuando se wiree el CLOB API live, esta fuente se reemplaza por una que consulte
Polymarket en tiempo real (misma interfaz).
"""
from __future__ import annotations

import os
import sqlite3
from decimal import Decimal
from pathlib import Path

from research.functions.market_scanner import PolymarketMarket
from research.schemas.match_prediction import MatchPrediction

HOME_WIN = "HOME_WIN"
AWAY_WIN = "AWAY_WIN"


def _db_path(tournament_id: str, data_root: str | os.PathLike | None) -> Path:
    root = Path(data_root or os.getenv("DATA_ROOT", "data"))
    return root / tournament_id / f"{tournament_id}.sqlite"


class SqliteOddsSource:
    """Lee cuotas reales del SQLite y las expone como mercados de Polymarket."""

    def __init__(
        self,
        tournament_id: str,
        *,
        source: str = "polymarket",
        connection: sqlite3.Connection | None = None,
        data_root: str | os.PathLike | None = None,
        default_volume_usdc: Decimal = Decimal("10000"),
        default_liquidity_usdc: Decimal = Decimal("10000"),
    ) -> None:
        self.tournament_id = tournament_id
        self.source = source
        self.default_volume_usdc = default_volume_usdc
        self.default_liquidity_usdc = default_liquidity_usdc
        if connection is not None:
            self._conn = connection
        else:
            path = _db_path(tournament_id, data_root)
            if not path.exists():
                raise FileNotFoundError(f"SQLite no encontrado: {path}")
            self._conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row

    def _odds_row(self, fixture_id: str) -> dict | None:
        try:
            cur = self._conn.execute(
                "SELECT * FROM polymarket_odds WHERE fixture_id=? AND source=? "
                "ORDER BY fetched_at DESC LIMIT 1",
                (fixture_id, self.source),
            )
        except sqlite3.OperationalError:
            return None  # tabla inexistente (DB sin cuotas migradas)
        row = cur.fetchone()
        return dict(row) if row else None

    def __call__(self, prediction: MatchPrediction) -> list[PolymarketMarket]:
        row = self._odds_row(prediction.event_id)
        if row is None:
            return []

        fid = prediction.event_id
        markets: list[PolymarketMarket] = []
        for outcome, prob_key in ((HOME_WIN, "home_prob"), (AWAY_WIN, "away_prob")):
            prob = row.get(prob_key)
            if prob is None:
                continue
            markets.append(
                PolymarketMarket(
                    condition_id=f"{fid}:{outcome}",
                    token_id=f"{fid}:{outcome}:YES",
                    outcome="YES",
                    model_outcome=outcome,
                    market_probability=Decimal(str(prob)),
                    volume_usdc=self.default_volume_usdc,
                    liquidity_usdc=self.default_liquidity_usdc,
                )
            )
        return markets
