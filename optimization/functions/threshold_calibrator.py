"""Calibración de thresholds por backtesting. Función pura.

Dado un historial de trades (cada uno con edge_at_entry y si ganó), barre
candidatos de `edge_threshold_auto` y reporta win_rate/ROI por threshold para
elegir el óptimo. No escribe a producción — sólo computa.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any


def backtest_thresholds(
    historical_trades: list[dict[str, Any]],
    *,
    candidates: list[Decimal] | None = None,
) -> dict[str, Any]:
    """Barre thresholds de edge y devuelve métricas por candidato + el mejor.

    Cada trade en `historical_trades` debe tener:
      - edge_at_entry: float|Decimal
      - won: bool
      - pnl: float|Decimal (opcional, para ROI)
      - size_usdc: float|Decimal (opcional, para ROI)
    """
    if candidates is None:
        candidates = [Decimal(c) / 100 for c in range(2, 16)]  # 0.02 .. 0.15

    results: list[dict[str, Any]] = []
    for thr in candidates:
        selected = [t for t in historical_trades if Decimal(str(t["edge_at_entry"])) >= thr]
        n = len(selected)
        wins = sum(1 for t in selected if t.get("won"))
        invested = sum(Decimal(str(t.get("size_usdc", 0))) for t in selected)
        pnl = sum(Decimal(str(t.get("pnl", 0))) for t in selected)
        win_rate = (wins / n) if n else 0.0
        roi = float(pnl / invested) if invested else 0.0
        results.append(
            {"threshold": thr, "n": n, "win_rate": win_rate, "roi": roi, "pnl": pnl}
        )

    # Mejor = mayor ROI con muestra mínima (n >= 10), o el de mayor ROI si ninguno.
    eligible = [r for r in results if r["n"] >= 10] or results
    best = max(eligible, key=lambda r: r["roi"]) if eligible else None
    return {"results": results, "best": best}
