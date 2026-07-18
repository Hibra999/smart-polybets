# EVOLUTION — theta_lay_v1 (doc-only)

> Estado actual (2026-07-18)
> **version**: 0.1 · **status**: draft
> **Postura**: draft, doc-only — no se carga vía `parse_strategy_md`/
> `load_active_strategy`; se opera a mano por CLI (`theta_monitor.py`) con
> `review_required: true`. La evidencia de concepto (WC 2026) es positiva pero
> no está validada con datos propios de Liga MX.
> **Preguntas abiertas**: ¿el decaimiento temporal + sobreprecio del favorito
> se replica con el spread/depth reales de Liga MX (mercado más ilíquido que
> el WC)? ¿el TP bruto de 5% sobrevive a fees + spread reales del round-trip?
> **Próximo paso**: validar con J1-J3 de Liga MX — recorder de ticks corriendo
> en cada jornada + 1-2 trades de sizing chico con `theta_monitor.py`, luego
> replicar el backtest sobre los ticks propios (spread/depth reales, no
> teóricos) antes de considerar mover a `under_review`.

---

### 2026-07-14 · v0.1 (génesis) · [FORMAL]
Estrategia de trading intradía (no bet-and-hold): comprar el NO del favorito al
kickoff en mercados "Will X win" (resuelven a 90') y salir vendiendo antes de
la resolución, monetizando el decaimiento temporal + el sobreprecio retail del
favorito (sesgo favorito-longshot). Declara `version: 0.1` / `status: draft`
desde el HEADER original. Marcada explícitamente **doc-only**: no pasa por
`StrategyConfig`/el loader canónico (usa campos propios del theta —
`min_fav_yes`, `entry_window_min`, etc. — no `edge_threshold_*`); se opera vía
CLI dirigida por el CIO. Este ledger se abre en bootstrap (2026-07-18) y
absorbe la historia previa:
- **2026-07-14** (`30d5285`): se construyen las piezas de ejecución —
  recorder de ticks (`scripts/record_market_ticks.py`, 1 snapshot/min de
  mercados winner/draw con book depth en ventana kickoff±) y el mecanismo de
  salida (`execution/functions/theta_exit.py`, regla pura TP/HARD/STOP) +
  `scripts/theta_monitor.py` (CLI con hard stop manual, dry-run por defecto).
- **2026-07-17** (`25a08ee`, `710d9f0`): auditoría de coherencia — **E4**: se
  marcó explícitamente el HEADER como doc-only (nota de que el loader canónico
  fallaría a propósito si se intentara cargar este STRATEGY.md).

### 2026-07-14 · [OBSERVACIÓN]
**Hipótesis**: comprar el NO del favorito al kickoff y vender antes de la
resolución captura decaimiento temporal + sobreprecio retail, con edge
positivo y creciente en el horizonte de salida.
**Resultado**: evidencia de concepto positiva sobre los 26 knockouts del WC
2026 con price history real de Polymarket (`scripts/wc_theta_trade_backtest.py`,
fidelity 1 min): +6.9% a los 30 min (17W-9L), +9.9% a 60 min, +15.7% a 90 min,
+21.4% a 105 min (15W-11L) — PnL bruto por share, monótono creciente con el
horizonte (consistente con decaimiento genuino, no ruido de apertura). Caveats
verificados: n=26 de un solo torneo (~1.2σ, dirección consistente pero no
significativa aún), ejecutabilidad in-play no probada (spread/liquidez fina,
2 cruces con taker fee ~5%, haircut estimado 3-6 pts de los 15-21 brutos), y
riesgo de gap si el favorito anota temprano (peor trade observado: -0.46/share,
Switzerland-Algeria).
**Disposición**: el CIO decidió (2026-07-14) apuntar la validación y la
eventual operación a **Liga MX con su propia data** — el Mundial ya terminó,
el backtest WC queda como evidencia de concepto, no como target de producción.
No se bumpea version (sin cambio de config; el hallazgo motivó construir el
recorder/monitor, ya absorbido en la génesis). Ver
`docs/findings/2026-07-14-theta-trade-lay-favorito.md`.
