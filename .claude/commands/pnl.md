---
description: Reportar PnL / cuenta (fuente de verdad = cuenta LIVE de Polymarket)
---
Ejecutá `python scripts/account.py --closed 300` y reportá:
1. **Equity total** = cash (pUSD) + Σ(posiciones abiertas mark-to-market).
2. Posiciones abiertas con uPnL.
3. Histórico resuelto: record W-L y **PnL neto**.

El PnL neto autoritativo es el de **flujo de caja** (línea "RESUELTAS … PnL neto"; = Σ ventas + Σ redenciones − Σ compras, cuadra con la UI). NO sumes solo el array `closed` a mano — subestima pérdidas (ver `docs/findings/2026-07-17-pnl-cashflow-vs-snapshot.md`).
