# 2026-07-17 — PnL neto: flujo de caja (cuadra con la UI) vs snapshot (sobreestima pérdidas)

## Síntoma
El histórico de PnL reportado (`account.py`) daba **−27.40 USDC**, pero la **UI de
Polymarket mostraba −19.58**. Gap de **7.82**, con `account.py` más negativo.

## Root cause (verificado por reconciliación)
`account.py`/`account_tools` calculaban el PnL de RESUELTAS por **snapshot**:

    realized_pnl de las cerradas/redimidas  +  (−invertido) por cada posición a $0

El SDK entrega las 13 posiciones perdedoras sin redimir con `cash_pnl = −invertido`
(percent_pnl −100%), así que el snapshot las cuenta como **pérdida total**. Pero eso
**ignora el salvamento de los cierres anticipados**: cuando una posición perdedora se
**vende antes de la resolución** (en vez de dejarla ir a $0), se recupera parte del
stake. Ese ingreso no aparece en el snapshot de posiciones.

El método correcto es el **flujo de caja real** de la wallet:

    PnL = Σ(ventas)  +  Σ(redenciones)  −  Σ(compras)

Reconciliación exacta con los datos live del 2026-07-17:

| Flujo | Monto |
|---|---|
| SELL (5 fills) | +146.59 |
| REDEEM (22) | +998.48 |
| BUY (42) | −1164.66 |
| **PnL neto** | **−19.58** ✓ = UI |

Las 5 ventas anticipadas incluían perdedoras salvadas: **Colombia 07-07** vendida
@0.17 (+11.71), **Egypt 07-03** @0.11 (+7.38), más el parcial de **Brazil 07-05**.
Ese salvamento (~+7.82 neto vs asumir pérdida total) es exactamente el gap.

## Relación con el gotcha del 2026-07-17 (array `closed`)
Es una **capa más profunda** del mismo problema. El gotcha anterior corrigió
+337.83 → −27.40 (dejar de leer solo `closed`, sumar también los perdedores a $0).
Pero se quedó en el método de snapshot, que **sigue ~$8 corto** cuando hubo cierres
anticipados. El flujo de caja es la única fórmula que cuadra con la UI.

## Fix aplicado
- `portfolio/schemas/account.py`: schemas `LiveTrade` (con `.usdc`) y `LiveRedemption`.
- `venue/gateway.py`: `trades()` (`list_trades`) y `redemptions()` (`list_activity`
  filtrando `type=REDEEM`) — **única capa que toca el SDK** (regla de oro #7).
- `portfolio/functions/pnl.py`: `realized_pnl_cashflow(trades, redemptions)` — función
  **pura**, testeada contra el fixture real (`tests/fixtures/pnl_cashflow_wc2026.json`,
  47 trades + 22 redeems → −19.58) en `tests/unit/test_pnl_cashflow.py`.
- `agent/tools/account_tools.py`: `account_snapshot` ahora trae `trades`, `redemptions`
  y `realized_pnl` (cash-flow). Tolerante: si la fuente no expone `get_trades`
  (fakes/fuentes viejas) → `realized_pnl=None` y el caller cae al snapshot.
- `scripts/account.py`: la línea `PnL neto` usa el cash-flow (−19.58); imprime una
  **reconciliación** (`Σ filas snapshot · salvamento · neto real`) para que las filas
  por-posición (que asumen pérdida total) no confundan. El `--json` expone
  `realized_pnl` + `trades` + `redemptions`.

## Regla para reportar PnL (actualiza la sección de CLAUDE.md)
El **PnL neto autoritativo es el de flujo de caja** (`account.py` ya lo muestra, o el
campo `realized_pnl` del `--json`). Las filas per-posición y el `cash_pnl` del SDK
asumen pérdida total en lo sin-redimir → **no** restar eso a mano; usar el neto de
`account.py`. La cifra sigue cuadrando con la UI de Polymarket (fuente de verdad).
