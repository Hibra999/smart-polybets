"""Test del SessionStore del CLI theta (persistencia de sesión y ticks)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.theta_monitor import SessionStore


def test_session_roundtrip(tmp_path):
    store = SessionStore(tmp_path / "ticks.sqlite")
    sid = store.open_session(started_at="2026-07-17T01:00:00", market="m",
                             token_id="tok", kickoff_utc="2026-07-17T01:00:00",
                             entry_price=0.48, shares=40.0, tp_pct=0.05,
                             from_min=30.0, hard_exit_min=105.0, stop_pct=None, live=0)
    assert sid == 1
    store.tick(ts_utc="t1", minute=31.0, best_bid=0.51, best_ask=0.53,
               bid_size=100.0, pnl_pct=0.0625, pnl_usdc=1.2, action="TP", note="ok")
    store.close_session(ended_at="t2", exit_reason="TP @ 0.51",
                        exit_price=0.51, pnl_usdc=1.2, order_id="ord1",
                        order_status="dry_run")
    row = store.con.execute(
        "SELECT exit_reason, exit_price, pnl_usdc, order_status FROM theta_session WHERE id=1"
    ).fetchone()
    assert row == ("TP @ 0.51", 0.51, 1.2, "dry_run")
    n = store.con.execute("SELECT COUNT(*) FROM theta_tick WHERE session_id=1").fetchone()[0]
    assert n == 1
