# tests/unit/test_account_tools.py
from datetime import datetime, timezone
from decimal import Decimal

from agent.tools import account_tools
from portfolio.schemas.account import (
    AccountBalance,
    ClosedPositionLive,
    LivePosition,
    OpenOrder,
)


class FakeSource:
    def get_balance(self):
        return AccountBalance(usdc_balance=Decimal("1000"),
                              as_of=datetime(2026, 7, 1, tzinfo=timezone.utc))

    def get_positions(self):
        return [LivePosition(condition_id="0xa", token_id="1", outcome="YES",
                             size_shares=Decimal("100"), avg_entry_price=Decimal("0.50"))]

    def get_open_orders(self):
        return [OpenOrder(order_id="o1", condition_id="0xa", token_id="1",
                          side="BUY", price=Decimal("0.55"), size_shares=Decimal("20"))]

    def get_closed_positions(self, limit=6):
        return [ClosedPositionLive(condition_id="0xb", token_id="2", outcome="YES",
                                   avg_price=Decimal("0.40"), realized_pnl=Decimal("12.50"))][:limit]


def _decisions():
    return [{"condition_id": "0xa", "tournament_id": "liga_mx_2026",
             "strategy_id": "match_winner_ligamx_v1", "status": "executed",
             "opportunity_json": {"event_id": "match_49", "polymarket_condition_id": "0xa"}}]


def test_snapshot_tags_and_marks():
    snap = account_tools.account_snapshot(
        FakeSource(), price_of=lambda p: Decimal("0.60"), decisions=_decisions())
    pos = snap["positions"][0]
    assert pos.event_id == "match_49"                 # tagged
    assert pos.unrealized_pnl == Decimal("10.0")   # marked
    assert snap["open_orders"][0].event_id == "match_49"
    assert snap["balance"].usdc_balance == Decimal("1000")
    assert snap["closed"][0].realized_pnl == Decimal("12.50")


def test_get_closed_positions_respects_limit():
    assert account_tools.get_closed_positions(FakeSource(), limit=0) == []
    assert len(account_tools.get_closed_positions(FakeSource(), limit=6)) == 1
