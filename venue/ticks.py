"""Extracción PURA de snapshots de mercado (ticks) desde eventos del SDK.

Convierte un MatchEvent (venue/discovery) en filas de tick listas para insertar:
precio (bid/ask/last/spread), volumen/liquidez, y estado del partido en vivo
(score/elapsed/period) cuando Polymarket lo publica. La profundidad del order
book la agrega el recorder (scripts/record_market_ticks.py) vía batch CLOB.

Sin red: funciones testeables con objetos fake (getattr/model_dump).
"""
from __future__ import annotations

import re

_WILL_WIN = re.compile(r"^Will .+ win", re.I)
_DRAW = re.compile(r"end in a draw", re.I)


def _f(x):
    return float(x) if x is not None else None


def market_kind(question: str) -> str | None:
    """'winner' | 'draw' para los mercados que trackeamos; None = ignorar."""
    if _WILL_WIN.match(question or ""):
        return "winner"
    if _DRAW.search(question or ""):
        return "draw"
    return None


def tick_rows_from_event(me, ts_utc: str) -> list[dict]:
    """Filas de tick de los mercados winner/draw de un MatchEvent."""
    ev = me.event
    sports = getattr(ev, "sports", None)
    sp = sports.model_dump() if sports is not None and hasattr(sports, "model_dump") else {}
    base = {
        "ts_utc": ts_utc,
        "event_id": str(getattr(ev, "id", "") or ""),
        "title": me.title,
        "kickoff_utc": me.kickoff.isoformat() if me.kickoff else None,
        "score": str(sp.get("score")) if sp.get("score") is not None else None,
        "elapsed": str(sp.get("elapsed")) if sp.get("elapsed") is not None else None,
        "period": sp.get("period"),
        "game_status": sp.get("game_status"),
    }
    rows: list[dict] = []
    for m in getattr(ev, "markets", None) or []:
        d = m.model_dump() if hasattr(m, "model_dump") else dict(m)
        q = d.get("question") or ""
        kind = market_kind(q)
        if kind is None:
            continue
        prices = d.get("prices") or {}
        metrics = d.get("metrics") or {}
        yes = (d.get("outcomes") or {}).get("yes") or {}
        rows.append({
            **base,
            "condition_id": d.get("condition_id"),
            "token_id": str(yes.get("token_id") or ""),
            "question": q,
            "market_kind": kind,
            "best_bid": _f(prices.get("best_bid")),
            "best_ask": _f(prices.get("best_ask")),
            "last_price": _f(prices.get("last_trade_price")),
            "spread": _f(prices.get("spread")),
            "volume": _f(metrics.get("volume_num") or metrics.get("volume")),
            "liquidity": _f(metrics.get("liquidity_num") or metrics.get("liquidity")),
            "bid_size": None, "ask_size": None,
            "bid_depth3": None, "ask_depth3": None,
        })
    return rows


def book_summary(book) -> dict:
    """Top-of-book y profundidad top-3 de un OrderBook del CLOB.

    bids/asks: listas de niveles con price/size; el mejor bid es el precio máximo
    y el mejor ask el mínimo (orden defensivo: no asumimos sorting del SDK).
    """
    d = book.model_dump() if hasattr(book, "model_dump") else dict(book)
    bids = sorted((dict(x) for x in d.get("bids") or []),
                  key=lambda x: float(x.get("price", 0)), reverse=True)
    asks = sorted((dict(x) for x in d.get("asks") or []),
                  key=lambda x: float(x.get("price", 1e9)))
    def top3(levels):
        return sum(float(x.get("size", 0)) for x in levels[:3]) or None
    return {
        "bid_size": float(bids[0]["size"]) if bids else None,
        "ask_size": float(asks[0]["size"]) if asks else None,
        "bid_depth3": top3(bids),
        "ask_depth3": top3(asks),
    }
