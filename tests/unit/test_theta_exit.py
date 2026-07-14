"""Tests de la regla de salida del theta trade (execution/functions/theta_exit.py)."""
from __future__ import annotations

from execution.functions.theta_exit import ThetaExitConfig, evaluate_exit

CFG = ThetaExitConfig(tp_pct=0.05, from_min=30, hard_exit_min=105, stop_pct=None)


def test_hold_before_from_min_even_if_profitable():
    action, _ = evaluate_exit(0.46, 0.55, minutes_since_kickoff=10, cfg=CFG)
    assert action is None  # +19.6% pero min 10 < 30: todavía no aplica el TP


def test_tp_fires_at_threshold_after_from_min():
    action, reason = evaluate_exit(0.46, 0.484, minutes_since_kickoff=45, cfg=CFG)
    assert action == "TP"          # +5.2% >= 5% al min 45
    assert "+5.2%" in reason
    action, _ = evaluate_exit(0.46, 0.48, minutes_since_kickoff=45, cfg=CFG)
    assert action is None          # +4.3% < 5%: hold


def test_hard_exit_fires_regardless_of_pnl():
    action, _ = evaluate_exit(0.46, 0.30, minutes_since_kickoff=106, cfg=CFG)
    assert action == "HARD"        # perdiendo -35% igual sale al min 105
    action, _ = evaluate_exit(0.46, None, minutes_since_kickoff=106, cfg=CFG)
    assert action == "HARD"        # sin bid, HARD igual dispara (reintento)


def test_stop_optional():
    cfg = ThetaExitConfig(tp_pct=0.05, from_min=30, hard_exit_min=105, stop_pct=0.25)
    action, _ = evaluate_exit(0.46, 0.34, minutes_since_kickoff=20, cfg=cfg)
    assert action == "STOP"        # -26.1% <= -25%
    action, _ = evaluate_exit(0.46, 0.36, minutes_since_kickoff=20, cfg=cfg)
    assert action is None          # -21.7%: aguanta


def test_no_bid_holds_before_hard():
    action, reason = evaluate_exit(0.46, None, minutes_since_kickoff=50, cfg=CFG)
    assert action is None and "sin bid" in reason
