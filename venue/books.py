"""Lecturas PÚBLICAS del CLOB (order books, price history) vía el SDK.

Mismo patrón que venue/discovery: los consumidores (scripts, monitors) NUNCA
tocan el PublicClient directo — todo acceso a Polymarket pasa por venue/
(regla de oro #7 del AGENTS.md). Cliente cacheado por proceso.

  order_book(token_id)      -> OrderBook de un token
  order_books(token_ids)    -> batch de OrderBooks (mismo orden que la entrada)
  price_history(token_id, start_ts, end_ts, fidelity) -> [(ts, price)]
  best_prices(book)         -> (best_bid, best_ask, bid_size) con orden defensivo
"""
from __future__ import annotations

from collections.abc import Sequence

import requests

from core.polymarket_client import build_public_client

CLOB_URL = "https://clob.polymarket.com"


def order_book(token_id: str):
    return build_public_client().get_order_book(token_id=token_id)


def order_books(token_ids: Sequence[str]):
    requested = list(token_ids)
    books = build_public_client().get_order_books(token_ids=requested)
    by_token = {str(book.token_id): book for book in books}
    return [by_token[token_id] for token_id in requested]


def price_history(token_id: str, *, start_ts: int | None = None,
                  end_ts: int | None = None, fidelity: int = 1) -> list[tuple[int, float]]:
    """Serie [(unix_ts, price)] del token (fidelity en minutos)."""
    hist = build_public_client().get_price_history(
        token_id=token_id, start_ts=start_ts, end_ts=end_ts, fidelity=fidelity)
    return [(d["t"], d["p"]) for d in (p.model_dump() for p in hist)]


def best_prices(book) -> tuple[float | None, float | None, float | None]:
    """(best_bid, best_ask, bid_size) de un OrderBook — orden defensivo, no
    asume que el SDK devuelva los niveles ordenados."""
    d = book.model_dump() if hasattr(book, "model_dump") else dict(book)
    bids = sorted((dict(x) for x in d.get("bids") or []),
                  key=lambda x: float(x.get("price", 0)), reverse=True)
    asks = sorted((dict(x) for x in d.get("asks") or []),
                  key=lambda x: float(x.get("price", 1e9)))
    bb = float(bids[0]["price"]) if bids else None
    ba = float(asks[0]["price"]) if asks else None
    bsz = float(bids[0]["size"]) if bids else None
    return bb, ba, bsz


def fee_rate_bps(token_id: str, *, session=requests) -> int:
    """Tasa vigente de un token; la API oficial la devuelve en basis points."""
    if not token_id:
        raise ValueError("token_id es obligatorio")
    response = session.get(
        f"{CLOB_URL}/fee-rate", params={"token_id": token_id}, timeout=10)
    response.raise_for_status()
    value = int(response.json()["base_fee"])
    if value < 0:
        raise ValueError("base_fee inválido")
    return value
