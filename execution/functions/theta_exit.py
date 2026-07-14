"""Regla de salida del theta trade (lay del favorito). Función PURA.

El trade: comprado NO del favorito al kickoff; se sale VENDIENDO antes de la
resolución. Reglas (todas configurables, evaluadas en este orden):
  1. HARD  — al minuto `hard_exit_min` (wall-clock desde kickoff) se vende
             SIEMPRE (horizonte del backtest: ~105 ≈ min 85 de juego).
  2. STOP  — si `stop_pct` está seteado y el PnL ≤ -stop_pct, se vende
             (nota: los goles del favorito gapean el precio; el stop limita
             el sangrado posterior, no el gap en sí).
  3. TP    — desde el minuto `from_min`: si el PnL ≥ `tp_pct`, se vende.

PnL evaluado contra el BEST BID (lo vendible AHORA), no contra mid/last —
conservador a propósito. `tp_pct` es bruto: debe cubrir fees de ida y vuelta
(~taker 5% sobre ganancias en mercados sports) — calibrar con los ticks de J1.

Finding: docs/findings/2026-07-14-theta-trade-lay-favorito.md
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ThetaExitConfig:
    tp_pct: float = 0.05        # take-profit sobre costo (0.05 = +5%)
    from_min: float = 30.0      # minuto (wall-clock) desde el cual aplica el TP
    hard_exit_min: float = 105.0  # salida forzada (fin del horizonte del trade)
    stop_pct: float | None = None  # stop-loss opcional (ej. 0.25); None = sin stop


def evaluate_exit(entry_price: float, best_bid: float | None,
                  minutes_since_kickoff: float,
                  cfg: ThetaExitConfig) -> tuple[str | None, str]:
    """(acción, razón). acción: None=hold | 'TP' | 'STOP' | 'HARD'."""
    if best_bid is None or best_bid <= 0:
        # sin bid no hay salida posible; HARD igual dispara para intentar
        if minutes_since_kickoff >= cfg.hard_exit_min:
            return "HARD", f"min {minutes_since_kickoff:.0f} >= {cfg.hard_exit_min:.0f} (sin bid: reintentar)"
        return None, "sin bid en el book"
    pnl = (best_bid - entry_price) / entry_price
    if minutes_since_kickoff >= cfg.hard_exit_min:
        return "HARD", f"min {minutes_since_kickoff:.0f} >= {cfg.hard_exit_min:.0f} (pnl {pnl:+.1%})"
    if cfg.stop_pct is not None and pnl <= -cfg.stop_pct:
        return "STOP", f"pnl {pnl:+.1%} <= -{cfg.stop_pct:.0%}"
    if minutes_since_kickoff >= cfg.from_min and pnl >= cfg.tp_pct:
        return "TP", f"pnl {pnl:+.1%} >= +{cfg.tp_pct:.0%} al min {minutes_since_kickoff:.0f}"
    return None, f"hold (pnl {pnl:+.1%}, min {minutes_since_kickoff:.0f})"
