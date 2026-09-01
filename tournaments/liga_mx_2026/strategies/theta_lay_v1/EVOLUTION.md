# EVOLUTION — theta_lay_v1

> **version**: 0.1 · **status**: draft · **alcance**: Liga MX

### 2026-07-18 · v0.1 · [FORMAL]

Se registró la hipótesis de comprar el token NO del favorito al kickoff y salir antes
de la resolución. Es doc-only: no pasa por `StrategyConfig`, siempre exige REVIEW y
se opera únicamente mediante el carril CIO y `theta_monitor.py`.

Piezas disponibles:

- recorder de ticks en `scripts/record_market_ticks.py`;
- regla pura TP/HARD/STOP en `execution/functions/theta_exit.py`;
- monitor dry-run por defecto en `scripts/theta_monitor.py`.

### Validación pendiente

No hay evidencia propia suficiente de Liga MX. Antes de proponer `under_review` se
requieren ticks de varias jornadas, PnL neto de fees/spread, profundidad ejecutable y
un backtest reproducible con esos datos. Ningún resultado cambia automáticamente la
versión, los límites o el estado.
