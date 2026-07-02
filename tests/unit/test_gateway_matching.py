"""Tests para Task 1.2: matching puro + find_match_markets del gateway.

TDD:
  - Step 1: este archivo  →  falla (ModuleNotFoundError: polymarket.matching).
  - Step 3: implementar   →  pasa.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from venue.matching import canon, match_event
from venue.gateway import PolymarketGateway
from research.functions.market_scanner import PolymarketMarket


# ── helpers: objetos fake que imitan el SDK Event / Market ──────────────────


class _FakeYesOutcome:
    def __init__(self, token_id: str, price: Decimal):
        self.label = "Yes"
        self.token_id = token_id
        self.price = price


class _FakeNoOutcome:
    def __init__(self):
        self.label = "No"
        self.token_id = "no-token"
        self.price = Decimal("0.40")


class _FakeOutcomes:
    def __init__(self, yes_token: str, yes_price: Decimal = Decimal("0.60")):
        self.yes = _FakeYesOutcome(yes_token, yes_price)
        self.no = _FakeNoOutcome()


class _FakePrices:
    def __init__(self, best_ask: Decimal | None = None, best_bid: Decimal | None = None):
        self.best_ask = best_ask
        self.best_bid = best_bid


class _FakeMetrics:
    def __init__(self, volume_num: Decimal = Decimal("1000"),
                 liquidity_num: Decimal = Decimal("500")):
        self.volume_num = volume_num
        self.liquidity_num = liquidity_num


class _FakeState:
    def __init__(self, accepting_orders: bool = True, neg_risk: bool = False):
        self.accepting_orders = accepting_orders
        self.neg_risk = neg_risk


class _FakeTrading:
    def __init__(self, tick: Decimal | None = Decimal("0.001"),
                 min_size: Decimal | None = Decimal("5")):
        self.minimum_tick_size = tick
        self.minimum_order_size = min_size


class _FakeMarket:
    def __init__(self, question: str, token_id: str,
                 condition_id: str = "cond-fake-1",
                 yes_price: Decimal = Decimal("0.60")):
        self.question = question
        self.condition_id = condition_id
        self.outcomes = _FakeOutcomes(token_id, yes_price)
        self.prices = _FakePrices(best_ask=yes_price)
        self.metrics = _FakeMetrics()
        self.state = _FakeState()
        self.trading = _FakeTrading()


class _FakeEvent:
    def __init__(self, title: str, markets: list[_FakeMarket]):
        self.title = title
        self.markets = markets


class _FakePage:
    def __init__(self, items): self.items = items


class _FakePaginator:
    def __init__(self, events): self._events = events
    def iter_items(self): return iter(self._events)


class _FakePubClient:
    def __init__(self, events): self._events = events
    def list_events(self, **kwargs): return _FakePaginator(self._events)


# ── tests: canon() ──────────────────────────────────────────────────────────


def test_canon_accent_cote_divoire():
    """Côte d'Ivoire → ivorycoast (accent + apostrophe + alias)."""
    assert canon("Côte d'Ivoire") == "ivorycoast"


def test_canon_accent_turkiye():
    """Türkiye → turkiye (umlaut stripped, no alias needed)."""
    assert canon("Türkiye") == "turkiye"


def test_canon_alias_turkey():
    """'Turkey' (Polymarket name) → 'turkiye' via alias."""
    assert canon("Turkey") == "turkiye"


def test_canon_alias_south_korea():
    assert canon("South Korea") == "korearepublic"


def test_canon_simple():
    """Plain ASCII names are just lowercased."""
    assert canon("Netherlands") == "netherlands"
    assert canon("Brazil") == "brazil"


def test_canon_alias_usa():
    assert canon("United States") == "usa"


# ── tests: match_event() ────────────────────────────────────────────────────


def test_match_event_netherlands_sweden_home_win():
    """'Netherlands vs. Sweden' → Netherlands is HOME_WIN."""
    mkt_ned = _FakeMarket("Will Netherlands win?", "tok-ned")
    mkt_swe = _FakeMarket("Will Sweden win?", "tok-swe")
    ev = _FakeEvent("Netherlands vs. Sweden", [mkt_ned, mkt_swe])

    results = match_event(ev, "Netherlands", "Sweden")

    assert results is not None
    assert len(results) == 2
    ned = next(r for r in results if r["model_outcome"] == "HOME_WIN")
    swe = next(r for r in results if r["model_outcome"] == "AWAY_WIN")
    assert ned["token_id"] == "tok-ned"
    assert swe["token_id"] == "tok-swe"


def test_match_event_no_match_returns_none():
    """Event for a different fixture returns None."""
    ev = _FakeEvent("Spain vs. Germany", [_FakeMarket("Will Spain win?", "t1")])
    assert match_event(ev, "Netherlands", "Sweden") is None


def test_match_event_only_win_markets():
    """A market without 'Will X win' pattern is ignored."""
    draw_mkt = _FakeMarket("Will there be a draw?", "tok-draw")
    win_mkt = _FakeMarket("Will Netherlands win?", "tok-ned")
    ev = _FakeEvent("Netherlands vs. Sweden", [draw_mkt, win_mkt])

    results = match_event(ev, "Netherlands", "Sweden")
    # Draw market is skipped ('draw' in q)
    assert results is not None
    assert len(results) == 1
    assert results[0]["model_outcome"] == "HOME_WIN"


def test_match_event_swapped_polymarket_order():
    """Polymarket may list 'away vs home'; matching should still map outcomes correctly."""
    mkt_swe = _FakeMarket("Will Sweden win?", "tok-swe")
    mkt_ned = _FakeMarket("Will Netherlands win?", "tok-ned")
    ev = _FakeEvent("Sweden vs. Netherlands", [mkt_swe, mkt_ned])

    results = match_event(ev, "Netherlands", "Sweden")
    assert results is not None
    ned = next((r for r in results if r["model_outcome"] == "HOME_WIN"), None)
    assert ned is not None
    assert ned["token_id"] == "tok-ned"


def test_match_event_with_accented_teams():
    """Accented names in event title are normalized before comparison."""
    mkt = _FakeMarket("Will Côte d'Ivoire win?", "tok-ci")
    ev = _FakeEvent("Côte d'Ivoire vs. Senegal", [mkt])
    results = match_event(ev, "Côte d'Ivoire", "Senegal")
    assert results is not None
    assert results[0]["model_outcome"] == "HOME_WIN"


# ── tests: PolymarketGateway.find_match_markets() ───────────────────────────


def _gw_with_pub(events: list) -> PolymarketGateway:
    gw = PolymarketGateway(live=False)
    gw._pub_client = _FakePubClient(events)
    return gw


def test_find_match_markets_returns_polymarket_markets():
    """find_match_markets returns list[PolymarketMarket]."""
    mkt_ned = _FakeMarket("Will Netherlands win?", "tok-ned", condition_id="cond-ned")
    mkt_swe = _FakeMarket("Will Sweden win?", "tok-swe", condition_id="cond-swe")
    ev = _FakeEvent("Netherlands vs. Sweden", [mkt_ned, mkt_swe])

    gw = _gw_with_pub([ev])
    result = gw.find_match_markets("Netherlands", "Sweden")

    assert isinstance(result, list)
    assert all(isinstance(m, PolymarketMarket) for m in result)
    assert len(result) == 2


def test_find_match_markets_correct_outcomes():
    """find_match_markets assigns HOME_WIN/AWAY_WIN correctly."""
    mkt_ned = _FakeMarket("Will Netherlands win?", "tok-ned",
                          yes_price=Decimal("0.65"))
    ev = _FakeEvent("Netherlands vs. Sweden", [mkt_ned])

    gw = _gw_with_pub([ev])
    result = gw.find_match_markets("Netherlands", "Sweden")

    assert len(result) == 1
    m = result[0]
    assert m.model_outcome == "HOME_WIN"
    assert m.token_id == "tok-ned"
    assert m.market_probability == Decimal("0.65")
    assert m.outcome == "YES"


def test_find_match_markets_no_match_returns_empty():
    """No matching event → empty list."""
    ev = _FakeEvent("Spain vs. Germany", [_FakeMarket("Will Spain win?", "t1")])
    gw = _gw_with_pub([ev])
    assert gw.find_match_markets("Netherlands", "Sweden") == []


def test_find_match_markets_multiple_events_only_one_matches():
    """Only the matching event's markets are returned."""
    ev1 = _FakeEvent("Spain vs. Germany", [_FakeMarket("Will Spain win?", "t1")])
    ev2 = _FakeEvent("Netherlands vs. Sweden", [
        _FakeMarket("Will Netherlands win?", "tok-ned"),
    ])
    gw = _gw_with_pub([ev1, ev2])
    result = gw.find_match_markets("Netherlands", "Sweden")
    assert len(result) == 1
    assert result[0].token_id == "tok-ned"
