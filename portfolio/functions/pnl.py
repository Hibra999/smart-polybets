"""PnL realizado por FLUJO DE CAJA — el método que cuadra con la UI de Polymarket.

El método de *snapshot* (sumar `realized_pnl` de posiciones cerradas + tratar las
posiciones sin redimir a $0 como pérdida total) **sobreestima las pérdidas** cuando
una posición perdedora se **cerró anticipadamente vendiendo** (salvamento que el
snapshot no ve). Ver `docs/findings/2026-07-17-pnl-cashflow-vs-snapshot.md`.

La fórmula correcta usa los flujos de caja reales de la wallet:

    PnL = Σ(ventas)  +  Σ(redenciones)  −  Σ(compras)

Función pura: mismos trades/redenciones → mismo número (principio rector).
"""
from __future__ import annotations

from decimal import Decimal

from portfolio.schemas.account import LiveRedemption, LiveTrade


def realized_pnl_cashflow(
    trades: list[LiveTrade], redemptions: list[LiveRedemption]
) -> Decimal:
    """PnL realizado = Σ ventas + Σ redenciones − Σ compras (todo en USDC)."""
    buys = sum((t.usdc for t in trades if t.side.upper() == "BUY"), Decimal("0"))
    sells = sum((t.usdc for t in trades if t.side.upper() == "SELL"), Decimal("0"))
    redeemed = sum((r.amount for r in redemptions), Decimal("0"))
    return sells + redeemed - buys
