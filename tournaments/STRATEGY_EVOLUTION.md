# Guía — Evolución de estrategias

Cada estrategia lleva un `EVOLUTION.md` append-only junto a su `STRATEGY.md`. Registra
su evolución para **auditar** (por qué estaba en el estado X en la versión N) y
**aprender** (qué se probó/descartó, qué sigue).

## Cuándo se registra
- **FORMAL** — en TODO cambio de `version` o `status` del `STRATEGY.md`. Atada a un
  diff del config + evidencia + nota de reproducibilidad.
- **OBSERVACIÓN** — cuando se prueba, descarta o pausa una idea SIN cambiar el config
  (hipótesis→prueba→resultado→disposición).

## Regla: cambio de config → bump de version
Cualquier cambio a los params/thresholds del `STRATEGY.md` **bumpea la `version`** y
lleva su entrada FORMAL. Esto NO es cosmético: la `version` es `strategy_version`, que
entra en la idempotency key (regla de oro #4) — si las reglas cambian pero la version no,
dos decisiones distintas comparten key. El validador (abajo) hace cumplir que la version
y la última FORMAL coincidan.

## Ciclo de vida y evidencia por transición
- `draft → under_review`: ≥1 OBSERVACIÓN con resultado + una hipótesis de edge.
- `under_review → approved`: entrada FORMAL que cite un **backtest con edge** (o
  evidencia live equivalente) + sizing definido.
- `* → deprecated`: entrada FORMAL con la razón del retiro.

## Formato (ver `EVOLUTION.md` de cualquier estrategia)
- Arriba, un bloque **Estado actual** (version · status · postura · preguntas abiertas ·
  próximo paso) — se reescribe cada sesión que toca la estrategia.
- Debajo, entradas reverse-cronológicas. Cabecera FORMAL: `### YYYY-MM-DD · vX→vY ·
  [FORMAL]` (o `vX (génesis)`); cabecera observación: `### YYYY-MM-DD · [OBSERVACIÓN]`.

## Validación
`python scripts/check_strategy_evolution.py` verifica que la última entrada FORMAL
declare la misma `version` que el `STRATEGY.md` (drift → exit 2). Advisory.

## Estrategias doc-only
Las que no se cargan por el pipeline (`theta_lay_v1`, marcada "Doc-only") igual llevan
`EVOLUTION.md`; el validador no compara contra el loader pero sí exige el ledger.
