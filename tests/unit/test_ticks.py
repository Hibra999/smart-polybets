"""Tests de venue/ticks.py (extracción pura de snapshots de mercado)."""
from __future__ import annotations

from datetime import UTC
from types import SimpleNamespace

from venue.ticks import book_summary, market_kind, tick_rows_from_event


def _mk(question, bid=0.30, ask=0.32, last=0.31, vol=1000.0):
    return SimpleNamespace(model_dump=lambda: {
        "question": question,
        "condition_id": "0xcond",
        "outcomes": {"yes": {"token_id": "tok_yes"}},
        "prices": {"best_bid": bid, "best_ask": ask, "last_trade_price": last,
                   "spread": ask - bid},
        "metrics": {"volume_num": vol, "liquidity_num": 500.0},
    })


def _event(markets, score=None, elapsed=None):
    ev = SimpleNamespace(
        id="701000",
        sports=SimpleNamespace(model_dump=lambda: {
            "score": score, "elapsed": elapsed, "period": None, "game_status": None}),
        markets=markets,
    )
    from datetime import datetime
    return SimpleNamespace(title="Necaxa vs. Atlante", kickoff=datetime(2026, 7, 17, 1, 0, tzinfo=UTC),
                           event=ev)


def test_market_kind_filters():
    assert market_kind("Will Club Necaxa win on 2026-07-16?") == "winner"
    assert market_kind("Will Necaxa vs. Atlante end in a draw?") == "draw"
    assert market_kind("Necaxa vs. Atlante: O/U 2.5") is None
    assert market_kind("Exact Score: Necaxa 1 - 0 Atlante?") is None


def test_tick_rows_extraction():
    me = _event([
        _mk("Will Club Necaxa win on 2026-07-16?"),
        _mk("Will Necaxa vs. Atlante end in a draw?", bid=0.28, ask=0.30),
        _mk("Necaxa vs. Atlante: O/U 2.5"),  # ignorado
    ], score="1-0", elapsed="37")
    rows = tick_rows_from_event(me, "2026-07-17T01:37:00+00:00")
    assert len(rows) == 2
    w = rows[0]
    assert w["market_kind"] == "winner"
    assert w["token_id"] == "tok_yes"
    assert w["best_bid"] == 0.30 and w["best_ask"] == 0.32
    assert w["score"] == "1-0" and w["elapsed"] == "37"
    assert w["bid_size"] is None  # depth la agrega el recorder, no la extracción


def test_book_summary_orders_levels_defensively():
    book = SimpleNamespace(model_dump=lambda: {
        "bids": [{"price": "0.28", "size": "100"}, {"price": "0.30", "size": "50"},
                 {"price": "0.27", "size": "200"}, {"price": "0.20", "size": "999"}],
        "asks": [{"price": "0.35", "size": "80"}, {"price": "0.32", "size": "40"}],
    })
    s = book_summary(book)
    assert s["bid_size"] == 50.0        # mejor bid = precio más alto (0.30)
    assert s["ask_size"] == 40.0        # mejor ask = precio más bajo (0.32)
    assert s["bid_depth3"] == 350.0     # top-3 bids: 50+100+200
    assert s["ask_depth3"] == 120.0


def test_book_summary_empty():
    book = SimpleNamespace(model_dump=lambda: {"bids": [], "asks": []})
    s = book_summary(book)
    assert s == {"bid_size": None, "ask_size": None, "bid_depth3": None, "ask_depth3": None}


def test_books_best_prices_defensive_order():
    from venue.books import ask_levels, best_prices
    book = SimpleNamespace(model_dump=lambda: {
        "bids": [{"price": "0.28", "size": "100"}, {"price": "0.30", "size": "50"}],
        "asks": [{"price": "0.35", "size": "80"}, {"price": "0.32", "size": "40"}],
    })
    bb, ba, bsz = best_prices(book)
    assert (bb, ba, bsz) == (0.30, 0.32, 50.0)
    assert ask_levels(book) == [(0.32, 40.0), (0.35, 80.0)]
    assert best_prices(SimpleNamespace(model_dump=dict)) == (None, None, None)
