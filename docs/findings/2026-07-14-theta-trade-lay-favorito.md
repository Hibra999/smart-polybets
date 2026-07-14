# 2026-07-14 — Theta trade: lay del favorito con salida anticipada (WC, precios reales de PM)

## Estrategia (propuesta del CIO)
En mercados "Will X win" a 90': comprar el **NO del favorito al kickoff** y
**cerrar vendiendo a los +X minutos** (sin llegar a resolución). Monetiza el
decaimiento temporal del favorito mientras el partido siga cerrado — y en PM,
el sobreprecio retail del favorito en knockouts (finding 2026-07-13: los "win a
90'" estaban sistemáticamente caros vs Poisson).

## Backtest con el price history REAL de Polymarket (fidelity=1 min)
`scripts/wc_theta_trade_backtest.py` — los 26 knockouts del WC 2026 con mercado
de ganador (favorito = mayor Yes 5 min pre-kickoff, ≥0.40; entrada al kickoff):
| Salida (wall-clock) | Record | PnL medio/share | ~% sobre costo |
|---|---|---|---|
| +30 min | 17W-9L | +0.027 | **+6.9%** |
| +60 min | 17W-9L | +0.039 | **+9.9%** |
| +90 min | 16W-10L | +0.062 | **+15.7%** |
| +105 min (≈min 85) | 15W-11L | +0.084 | **+21.4%** |
- Peor trade: Switzerland-Algeria (fav 0.49→0.95, -0.46/share). Mejores: England-DRC
  (+0.53), Argentina-Egypt (+0.50), Belgium-Senegal (+0.50).
- El PnL crece monótono con el horizonte → es decaimiento genuino, no un tick de apertura.

## Caveats (por qué NO es todavía una estrategia aprobable)
1. **n=26, un solo torneo**: σ por trade ≈0.25 → el +0.062 (90min) es ~1.2σ. La
   DIRECCIÓN es consistente en 4 horizontes, pero no es significativo aún.
2. **Ejecutabilidad**: el history es precio de trade (mid-ish). In-play el spread
   se abre y la liquidez es fina; son 2 cruces (entrada+salida) con taker fee ~5%.
   Haircut realista ~3-6 pts de los ~15-21 → el neto probable es positivo pero
   menor. Mitigación: piernas maker (rebate) cuando el tiempo lo permita.
3. **Riesgo de gap**: si el favorito anota temprano no hay stop que funcione (el
   precio salta). El -0.46 de Switzerland-Algeria es el tail real. Sizing chico.
4. **Coherencia con findings previos**: este edge ES la contracara monetizable del
   sesgo documentado (retail sobreprecia favoritos a 90' en eliminatorias +
   favorite-longshot bias). No contradice el "sin edge de modelo": no requiere
   modelo, requiere que el venue sea retail.

## Decisión del CIO (2026-07-14): la estrategia apunta a LIGA MX
El Mundial ya terminó — el backtest WC es evidencia de concepto, no el target.
No contaminar la estrategia entre torneos: la validación y la eventual operación
son sobre Liga MX con SU propia data.

## Próximos pasos antes de operar
1. **✅ HECHO — Recorder de ticks** (`scripts/record_market_ticks.py`): 1 snapshot/min
   de todos los mercados winner/draw abiertos de Liga MX (bid/ask/last/spread/vol/
   liquidez + score en vivo), y **profundidad del book** (top-of-book + top-3, batch
   CLOB) en la ventana activa kickoff-60min → +150min. DB: `market_ticks.sqlite`
   (WAL, gitignored). Correr durante las jornadas desde la J1 (jueves 2026-07-16).
2. **✅ HECHO — Mecanismo de salida** (cierra el ciclo):
   - Regla PURA en `execution/functions/theta_exit.py` (testeada): **TP** si
     PnL ≥ `tp_pct` (default +5%, sobre el best bid = lo vendible YA) desde el
     minuto `from_min` (default 30) · **HARD** al minuto `hard_exit_min`
     (default 105) pase lo que pase · **STOP** opcional.
   - **CLI operable** `scripts/theta_monitor.py`: lee el book vía `venue/books`
     (~460ms medido) cada 5s, imprime lectura+PnL en cada tick, evalúa y VENDE
     automático al disparo (LIMIT al best bid, 3 reintentos con bid fresco).
     Comandos en vivo: `v`+Enter = **hard stop manual** (vende YA), `p` = PnL,
     `q`/Ctrl+C = salir sin vender. Persiste TODO en `theta_session`/`theta_tick`
     (market_ticks.sqlite, WAL): lecturas, PnL, intentos y errores de venta —
     si la venta falla tras los reintentos, imprime resumen + instrucciones y
     nada se pierde. Dry-run default; live con gates + confirmación tipeada AL
     INICIO (no al disparo — ahí importa la velocidad). La venta no pasa por el
     ledger → asentar con backfill_manual_trades.py. Hard stop verificado
     end-to-end en dry-run (comando `v` → venta simulada + sesión persistida).
   - Medido pre-J1: NO-Necaxa bid 0.48 con 968 shares y spread 0.03 — la
     liquidez pre-partido alcanza para el sizing de prueba.
3. **Plan J1 (2026-07-16/17)**: jornada de warmup de los otros modelos (no
   apuestan) → probar el ciclo completo con sizing chico: entrada del NO del
   favorito vía propose_bet/orders al kickoff + theta_monitor con TP 5%/min 30 +
   recorder corriendo en paralelo. El TP de 5% es bruto: validar contra fees
   reales del round-trip con los datos grabados.
4. Con 2-3 jornadas grabadas: replicar el backtest sobre ticks PROPIOS de Liga MX
   (con spread/depth reales → PnL ejecutable, no teórico).
5. Extender el backtest WC a los ~100 partidos (grupos) — opcional, la evidencia
   que importa será la de Liga MX.

## Agenda de análisis para afinar la estrategia (con los events/ capturados)
Datos: `data/<tid>/events/<fecha>-<evento>/ticks.sqlite` (1/min todos los mercados
+ 5s book del monitor + score live). Primer dataset: France-Spain SF 2026-07-14
(incluye un penal → gol: el caso de estrés perfecto).
1. **Latencia de repricing tras eventos**: ticks 5s alrededor del penal/gol —
   ¿cuántos segundos tarda el book en llegar al precio nuevo? Define si la salida
   "al bid" es realista tras un gol o si siempre llegamos tarde.
2. **Evaporación de profundidad**: bid_size antes/durante/después del evento
   (visto en vivo: 14,000 → 13.5 shares durante el penal). Define el sizing máximo
   ejecutable y si conviene salida escalonada (vender en 2-3 clips).
3. **Spread in-play por minuto**: curva spread(t) + en eventos → costo real del
   round-trip. Con eso, pasar `tp_pct` de bruto a NETO (fees ~5% taker + spread).
4. **Curva de decay real del favorito en 0-0** (ticks 1/min): pendiente por minuto
   vs la del backtest (history 1-min de PM) → recalibrar `from_min` y
   `hard_exit_min` (¿105 es óptimo o el theta se concentra 60-90?).
5. **Lag Gamma vs CLOB cuantificado**: mismo instante, precio del recorder (gamma)
   vs book del monitor (visto: gamma 0.3125 mientras el book estaba 0.4625).
   Regla operativa: valuación/ejecución in-play SOLO con book; score feed solo
   para etiquetar post-hoc (también llega tarde).
6. **Correlación draw↔favorito in-play**: ¿sirve el mercado de empate como hedge
   del gap por gol? (versión theta con cobertura parcial).
7. **Fees reales del round-trip**: primer trade real chico en J1 → medir fee
   efectivo cobrado y slippage de las dos piernas; ajustar el TP mínimo.
8. **Asimetría 1er tiempo / 2do tiempo**: ¿el theta decae linealmente o se acelera
   post-descanso? (ajustar from_min por mitades).
3. Si sobrevive: proponer estrategia `theta_lay_v1` (draft) con reglas en STRATEGY.md
   (entrada kickoff, salida +90/+105 o al gol del favorito, sizing fijo chico,
   solo mercados con volumen mínimo) y carril de ejecución con SELL (el broker ya
   soporta OrderSide.SELL; falta workflow de cierre de posición en orders.py).
