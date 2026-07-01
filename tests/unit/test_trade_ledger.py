"""Tests del ledger de trades (clasificación + PnL asentado)."""
from __future__ import annotations

from decimal import Decimal

from portfolio.functions.trade_ledger import (
    HOME_WIN,
    LOST,
    OPEN,
    UNGRADED,
    WON,
    build_ledger,
    settle_pnl,
)


def _dec(status, event_id, side="HOME_WIN", price="0.50", size="100", verdict="AUTO"):
    return {
        "idempotency_key": f"key_{event_id}_{status}",
        "tournament_id": "fifa_world_cup_2026",
        "sport": "football",
        "strategy_id": "match_winner_wc_v1",
        "status": status,
        "verdict": verdict,
        "pick_side": side,
        "pick_participant": "Home FC" if side == HOME_WIN else "Away FC",
        "recommended_size": size,
        "edge": "0.10",
        "order_result": {"avg_price": price, "filled_size_usdc": size},
        "opportunity_json": {
            "event_id": event_id,
            "participant_home": "Home FC",
            "participant_away": "Away FC",
            "event_start_utc": "2026-06-20T13:00:00Z",
            "best_ask": price,
            "model_outcome": side,
        },
    }


def test_settle_pnl_win_and_loss():
    # comprado a 0.50, ganado → +stake (payout 2x)
    assert settle_pnl(Decimal("100"), Decimal("0.50"), WON) == Decimal("100")
    # comprado a 0.25, ganado → +3x stake
    assert settle_pnl(Decimal("100"), Decimal("0.25"), WON) == Decimal("300")
    # perdido → -stake
    assert settle_pnl(Decimal("100"), Decimal("0.50"), LOST) == Decimal("-100")


def test_open_position_when_fixture_not_finished():
    decisions = [_dec("executed", "wc_1")]
    results = {"wc_1": {"status": "scheduled"}}
    led = build_ledger(decisions, results, bankroll=1000)
    assert led["summary"]["n_open"] == 1
    assert led["open"][0]["outcome"] == OPEN


def test_closed_win_settles_pnl():
    decisions = [_dec("executed", "wc_1", side=HOME_WIN, price="0.50", size="100")]
    results = {"wc_1": {"status": "finished", "home_team_id": "home",
                        "away_team_id": "away", "winner_team_id": "home"}}
    led = build_ledger(decisions, results, bankroll=1000)
    assert led["summary"]["n_closed"] == 1
    assert led["summary"]["wins"] == 1
    assert led["closed"][0]["outcome"] == WON
    assert led["closed"][0]["pnl"] == Decimal("100")
    assert led["summary"]["realized_pnl"] == Decimal("100")


def test_closed_loss_on_draw():
    # apuesta a HOME_WIN pero el partido fue empate (winner NULL) → pierde
    decisions = [_dec("executed", "wc_1", side=HOME_WIN, price="0.40", size="50")]
    results = {"wc_1": {"status": "finished", "home_team_id": "home",
                        "away_team_id": "away", "winner_team_id": None}}
    led = build_ledger(decisions, results, bankroll=1000)
    assert led["closed"][0]["outcome"] == LOST
    assert led["closed"][0]["pnl"] == Decimal("-50")


def test_ungraded_when_pick_side_missing():
    dec = _dec("executed", "wc_1")
    dec["pick_side"] = None
    dec["opportunity_json"]["model_outcome"] = None
    results = {"wc_1": {"status": "finished", "home_team_id": "home",
                        "away_team_id": "away", "winner_team_id": "home"}}
    led = build_ledger([dec], results, bankroll=1000)
    assert led["open"][0]["outcome"] == UNGRADED  # no se asienta sin el lado


def test_pending_decision_not_counted_as_trade():
    decisions = [_dec("pending_approval", "wc_1", verdict="REVIEW")]
    led = build_ledger(decisions, {}, bankroll=1000)
    assert led["summary"]["n_pending"] == 1
    assert led["summary"]["n_open"] == 0
    assert led["summary"]["n_closed"] == 0
