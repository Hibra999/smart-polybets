"""Fuente de mercados LIVE desde el Gamma API de Polymarket (read-only).

Trae los eventos del Mundial 2026 (tag 102232), parsea los mercados de ganador por
partido ("Will {team} win…?" Yes/No) y captura lo que hace falta para una orden real:
  - `token_id` real (clobTokenIds del outcome YES)
  - `condition_id` real
  - precio live (bestAsk/bestBid/outcomePrices)
  - `neg_risk`, `tick_size` (orderPriceMinTickSize), `min_order_size` (orderMinSize)

Resuelve los gaps #2 (token ids reales) y #3 (precio live) para poder apostar.
El matching partido→mercado replica la normalización validada de
pypro_worldcup_betting (135/135 partidos).

NO coloca órdenes: sólo lee. La ejecución vive en execution/ (broker).
"""
from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal

import requests

from research.functions.market_scanner import PolymarketMarket
from research.schemas.match_prediction import MatchPrediction

GAMMA = "https://gamma-api.polymarket.com"
WORLD_CUP_TAG_ID = 102232
_UA = {"User-Agent": "Mozilla/5.0 (sports-quant-trading; +https://polymarket.com)"}

# Alias de nombres (Polymarket/inglés → canónico del proyecto), portado de
# scraper.ALT_NAME_MAP de pypro_worldcup_betting + variantes Polymarket.
_ALIASES = {
    "cote divoire": "ivory coast", "cotedivoire": "ivory coast",
    "dr congo": "congo dr", "drcongo": "congo dr",
    "bosnia and herzegovina": "bosnia herzegovina",
    "cabo verde": "cape verde",
    "turkey": "turkiye",
    "czech republic": "czechia",
    "south korea": "korea republic", "korea": "korea republic",
    "united states": "usa", "united states of america": "usa",
}
_WILL_WIN_RE = re.compile(r"\s*will\s+(.+?)\s+win\b", re.I)


def _canon(name: str) -> str:
    """Clave de comparación: sin acentos, minúsculas, sólo alfanumérico, con alias."""
    n = unicodedata.normalize("NFKD", (name or "")).encode("ascii", "ignore").decode()
    n = re.sub(r"[^a-z0-9 ]", "", n.lower()).strip()
    n = _ALIASES.get(n, n)
    n = _ALIASES.get(n.replace(" ", ""), n)
    return n.replace(" ", "")


class PolymarketLiveSource:
    """market_source que consulta el Gamma API en vivo (read-only)."""

    def __init__(self, *, tag_id: int = WORLD_CUP_TAG_ID, max_events: int = 800,
                 timeout: int = 20, accepting_only: bool = True,
                 session: requests.Session | None = None) -> None:
        self.tag_id = tag_id
        self.max_events = max_events
        self.timeout = timeout
        self.accepting_only = accepting_only
        self._session = session or requests.Session()
        self._index: dict[frozenset, dict] | None = None  # {frozenset(home,away): {team_key: market}}

    # ── fetch ────────────────────────────────────────────────────────────────

    def _fetch_events(self) -> list[dict]:
        events: list[dict] = []
        offset = 0
        while len(events) < self.max_events:
            params = {"tag_id": self.tag_id, "limit": 100, "offset": offset, "closed": "false"}
            resp = self._session.get(f"{GAMMA}/events", params=params,
                                     headers=_UA, timeout=self.timeout)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            events.extend(batch)
            if len(batch) < 100:
                break
            offset += 100
        return events

    def _win_market(self, mkt: dict, model_outcome: str) -> dict | None:
        """Extrae los datos de orden de un mercado 'Will X win' (outcome YES)."""
        try:
            labels = [str(o).strip().lower() for o in json.loads(mkt["outcomes"])]
            prices = [Decimal(str(p)) for p in json.loads(mkt["outcomePrices"])]
            token_ids = json.loads(mkt["clobTokenIds"])
        except (KeyError, ValueError, TypeError):
            return None
        if set(labels) != {"yes", "no"}:
            return None
        yi = labels.index("yes")
        return {
            "model_outcome": model_outcome,
            "token_id": str(token_ids[yi]),
            "condition_id": mkt.get("conditionId", ""),
            "yes_price": prices[yi],
            "best_ask": Decimal(str(mkt["bestAsk"])) if mkt.get("bestAsk") is not None else None,
            "best_bid": Decimal(str(mkt["bestBid"])) if mkt.get("bestBid") is not None else None,
            "neg_risk": bool(mkt.get("negRisk", False)),
            "tick_size": Decimal(str(mkt["orderPriceMinTickSize"]))
            if mkt.get("orderPriceMinTickSize") is not None else None,
            "min_order_size": Decimal(str(mkt["orderMinSize"]))
            if mkt.get("orderMinSize") is not None else None,
            "accepting_orders": bool(mkt.get("acceptingOrders", False)),
            "volume": Decimal(str(mkt.get("volumeNum") or mkt.get("volume") or 0)),
            "liquidity": Decimal(str(mkt.get("liquidityNum") or mkt.get("liquidity") or 0)),
        }

    def _build_index(self) -> dict[frozenset, dict]:
        index: dict[frozenset, dict] = {}
        for ev in self._fetch_events():
            title = (ev.get("title") or "").split(" - ")[0]
            m = re.match(r"^(.+?)\s+vs\.?\s+(.+?)\??$", title, re.I)
            if not m:
                continue
            home_k, away_k = _canon(m.group(1)), _canon(m.group(2))
            per_team: dict[str, dict] = {}
            for mkt in (ev.get("markets") or []):
                q = mkt.get("question") or ""
                if "draw" in q.lower():
                    continue
                wm = _WILL_WIN_RE.match(q)
                if not wm:
                    continue
                team_k = _canon(wm.group(1))
                outcome = "HOME_WIN" if team_k == home_k else (
                    "AWAY_WIN" if team_k == away_k else None)
                if outcome is None:
                    continue
                info = self._win_market(mkt, outcome)
                if info:
                    per_team[team_k] = info
            if home_k in per_team and away_k in per_team:
                index[frozenset((home_k, away_k))] = per_team
        return index

    def _ensure_index(self) -> dict[frozenset, dict]:
        if self._index is None:
            self._index = self._build_index()
        return self._index

    def refresh(self) -> None:
        """Fuerza re-fetch (precios live cambian; llamar antes de cada decisión)."""
        self._index = None

    # ── market_source API ────────────────────────────────────────────────────

    def __call__(self, prediction: MatchPrediction) -> list[PolymarketMarket]:
        index = self._ensure_index()
        hk, ak = _canon(prediction.participant_home), _canon(prediction.participant_away)
        per_team = index.get(frozenset((hk, ak)))
        if not per_team:
            return []
        markets: list[PolymarketMarket] = []
        for team_k, info in per_team.items():
            if self.accepting_only and not info["accepting_orders"]:
                continue
            # CRÍTICO: el outcome se asigna según el home/away de NUESTRA predicción,
            # no del título de Polymarket (el orden puede diferir).
            if team_k == hk:
                outcome = "HOME_WIN"
            elif team_k == ak:
                outcome = "AWAY_WIN"
            else:
                continue
            # precio del modelo de mercado = midpoint; el order price usa best_ask
            mid = info["yes_price"]
            markets.append(PolymarketMarket(
                condition_id=info["condition_id"],
                token_id=info["token_id"],
                outcome="YES",
                model_outcome=outcome,
                market_probability=mid,
                volume_usdc=info["volume"],
                liquidity_usdc=info["liquidity"],
                best_ask=info["best_ask"],
                best_bid=info["best_bid"],
                neg_risk=info["neg_risk"],
                tick_size=info["tick_size"],
                min_order_size=info["min_order_size"],
                accepting_orders=info["accepting_orders"],
            ))
        return markets
