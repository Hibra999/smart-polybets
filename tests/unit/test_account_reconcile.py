# tests/unit/test_account_reconcile.py
from datetime import datetime, timezone
from decimal import Decimal

from portfolio.functions.account_reconcile import (
    index_decisions_by_condition,
    mark_to_market,
    reconcile,
    tag_positions,
)
from portfolio.schemas.account import AccountBalance, LivePosition


def _pos(cid, token="1", entry="0.50", shares="100"):
    return LivePosition(condition_id=cid, token_id=token, outcome="YES",
                        size_shares=Decimal(shares), avg_entry_price=Decimal(entry))


def _dec(cid, event_id="wc_1", status="executed"):
    return {
        "condition_id": cid,
        "tournament_id": "fifa_world_cup_2026",
        "strategy_id": "match_winner_wc_v1",
        "status": status,
        "opportunity_json": {"event_id": event_id, "polymarket_condition_id": cid},
    }


def test_mark_to_market_sets_price_and_derives_pnl():
    marked = mark_to_market([_pos("0xa")], price_of=lambda p: Decimal("0.60"))
    assert marked[0].current_price == Decimal("0.60")
    assert marked[0].unrealized_pnl == Decimal("10.0")


def test_mark_to_market_leaves_none_when_no_price():
    marked = mark_to_market([_pos("0xa")], price_of=lambda p: None)
    assert marked[0].current_price is None
    assert marked[0].unrealized_pnl is None


def test_tag_positions_maps_known_and_leaves_external():
    positions = [_pos("0xa"), _pos("0xEXT")]
    tagged = tag_positions(positions, [_dec("0xa", event_id="wc_49")])
    by_cid = {p.condition_id: p for p in tagged}
    assert by_cid["0xa"].event_id == "wc_49"
    assert by_cid["0xa"].tournament_id == "fifa_world_cup_2026"
    assert by_cid["0xEXT"].event_id is None       # externa


def test_index_by_condition_reads_both_shapes():
    idx = index_decisions_by_condition([
        {"condition_id": "0xa"},
        {"opportunity_json": {"polymarket_condition_id": "0xb"}},
    ])
    assert set(idx) == {"0xa", "0xb"}


def test_reconcile_reports_delta_missing_fills_and_external():
    balance = AccountBalance(usdc_balance=Decimal("1200"),
                             as_of=datetime(2026, 7, 1, tzinfo=timezone.utc))
    decisions = [_dec("0xIN"), _dec("0xNOFILL")]   # dos ejecutadas locales
    positions = [_pos("0xIN"), _pos("0xEXT")]      # una casa, otra es externa
    rep = reconcile(decisions, balance, positions, bankroll_param=Decimal("1000"))
    assert rep["bankroll_delta"] == Decimal("200")
    assert rep["missing_fills"] == ["0xNOFILL"]    # ejecutada local sin posición on-chain
    assert rep["external_positions"] == ["0xEXT"]  # posición on-chain sin decisión local
    assert rep["n_live_positions"] == 2
    assert rep["n_executed_local"] == 2
