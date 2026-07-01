"""Fuente de mercados de GOLES (Over/Under, BTTS) del Gamma API de Polymarket.

Complementa polymarket_live (que sólo parsea "Will X win"). Los mercados de goles
viven en un evento aparte "{Local} vs. {Visita} - More Markets", con questions
prefijadas "{Local} vs. {Visita}: O/U 2.5" / ": Both Teams to Score".

Devuelve lo necesario para firmar una orden real sobre el outcome elegido (Over por
defecto): token_id, condition_id, precio (best_ask/mid), neg_risk, tick, min_size.
Read-only: no coloca órdenes.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal

import requests

from research.functions.polymarket_live import _canon

GAMMA = "https://gamma-api.polymarket.com"
WORLD_CUP_TAG_ID = 102232
_UA = {"User-Agent": "Mozilla/5.0 (sports-quant-trading)"}
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


def _fetch_events(tag_id: int, timeout: int, session: requests.Session) -> list[dict]:
    out: list[dict] = []
    off = 0
    while len(out) < 1200:
        resp = session.get(f"{GAMMA}/events",
                           params={"tag_id": tag_id, "limit": 100, "offset": off, "closed": "false"},
                           headers=_UA, timeout=timeout)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        out += batch
        if len(batch) < 100:
            break
        off += 100
    return out


def _market_outcome(mkt: dict, want_label: str) -> GoalsMarket | None:
    try:
        labels = json.loads(mkt["outcomes"])
        prices = [Decimal(str(p)) for p in json.loads(mkt["outcomePrices"])]
        tokens = json.loads(mkt["clobTokenIds"])
    except (KeyError, ValueError, TypeError):
        return None
    low = [str(x).strip().lower() for x in labels]
    if want_label.lower() not in low:
        return None
    i = low.index(want_label.lower())
    return GoalsMarket(
        question=mkt.get("question", ""),
        outcome_label=str(labels[i]),
        token_id=str(tokens[i]),
        condition_id=mkt.get("conditionId", ""),
        price=prices[i],
        best_ask=Decimal(str(mkt["bestAsk"])) if mkt.get("bestAsk") is not None else None,
        neg_risk=bool(mkt.get("negRisk", False)),
        tick_size=Decimal(str(mkt["orderPriceMinTickSize"]))
        if mkt.get("orderPriceMinTickSize") is not None else None,
        min_order_size=Decimal(str(mkt["orderMinSize"]))
        if mkt.get("orderMinSize") is not None else None,
        accepting_orders=bool(mkt.get("acceptingOrders", False)),
    )


def fetch_goals_market(home: str, away: str, *, kind: str = "ou", line: float = 2.5,
                       outcome: str = "Over", tag_id: int = WORLD_CUP_TAG_ID,
                       timeout: int = 20, session: requests.Session | None = None
                       ) -> GoalsMarket | None:
    """Busca el mercado de goles de un partido y devuelve el outcome pedido.

    kind="ou"  -> "{H} vs. {A}: O/U {line}"   (outcome "Over"/"Under")
    kind="btts" -> "{H} vs. {A}: Both Teams to Score" (outcome "Yes"/"No")
    El matching de equipos usa la normalización canónica validada.
    """
    sess = session or requests.Session()
    hk, ak = _canon(home.replace("_", " ")), _canon(away.replace("_", " "))
    if kind == "ou":
        suffix = f": O/U {line:g}"
    elif kind == "btts":
        suffix = ": Both Teams to Score"
    else:
        raise ValueError(f"kind desconocido: {kind}")

    for ev in _fetch_events(tag_id, timeout, sess):
        title = ev.get("title") or ""
        m = _MORE.match(title)
        if not m:
            continue
        if {_canon(m.group(1)), _canon(m.group(2))} != {hk, ak}:
            continue
        for mkt in (ev.get("markets") or []):
            q = mkt.get("question", "")
            if kind == "btts":
                if q.strip().endswith("Both Teams to Score"):
                    return _market_outcome(mkt, outcome)
            elif q.strip().endswith(suffix):
                return _market_outcome(mkt, outcome)
    return None
