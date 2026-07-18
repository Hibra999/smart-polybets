# Diseño — Registro de evolución de estrategias (`EVOLUTION.md` + guía + validador)

**Fecha:** 2026-07-18
**Estado:** aprobado (brainstorming) — pendiente plan de implementación

## Problema

Las estrategias evolucionan sesión a sesión (el `match_winner_wc_v1` del Mundial es
el caso testigo), pero **no hay un proceso estandarizado que registre esa evolución
ni sus razones**. El "por qué" quedó disperso en commits de git, `docs/findings/` y la
cabeza del CIO. Falta un artefacto por estrategia que ligue cada cambio a su evidencia
y deje el estado del pensamiento para la próxima sesión. Ya existe un draft para Liga MX
(`match_winner_ligamx_v1`); falta la guía que gobierne su evolución natural.

## Decisiones (brainstorming)

1. **Propósito: auditar Y aprender** por igual — cada entrada liga una decisión a su
   evidencia (auditable) y deja postura/próximo paso (accionable).
2. **Dos tipos de entrada**: FORMAL (bump de version / cambio de status, atado a diff
   del config + evidencia) y OBSERVACIÓN (hipótesis→prueba→resultado→disposición, sin
   cambio de config). Registrar solo cambios de config perdería el "consideramos X y lo
   descartamos" — el hueco del WC.
3. **Enfoque A**: un `EVOLUTION.md` append-only por estrategia, junto al `STRATEGY.md`.
4. **Reverse-cronológico** con un bloque **Estado actual** arriba.
5. **Validador CLI aparte** (`scripts/check_strategy_evolution.py`), no fusionado en
   `check_freshness` (es gobernanza de estrategia, no frescura de datos). Advisory.
6. **Bootstrap best-effort del WC** (reconstruir hitos desde git/findings) + genesis
   para las demás estrategias.

## Principio rector aplicado

Reproducibilidad: cada entrada FORMAL incluye la **evidencia** y la **base de datos/
inputs** que respaldan la decisión, de modo que "por qué la estrategia estaba en el
estado X en la versión N" sea reconstruible. Encaja con la regla de oro #5 (todo lo
generado lleva `strategy_version`) y con la capa de precondiciones ya existente.

## Pieza 1 — El ledger: `tournaments/<t>/strategies/<s>/EVOLUTION.md`

Append-only. Estructura:

```markdown
# EVOLUTION — <strategy_id>

> **Estado actual (YYYY-MM-DD)** · v<version> · <status>
> Postura: <una línea>.
> Preguntas abiertas: <bullets>.
> Próximo paso: <acción concreta>.

---

### YYYY-MM-DD · v<from>→v<to> · [FORMAL]
- **Cambio**: <status y/o params, resumen del diff del config>
- **Razón**: <por qué>
- **Evidencia**: <links a docs/findings/*, backtests, observaciones de mercado>
- **Reproducibilidad**: <inputs / versión de datos que respaldan la decisión>

### YYYY-MM-DD · [OBSERVACIÓN]
- **Hipótesis**: <...>
- **Prueba**: <qué se corrió / qué se miró>
- **Resultado**: <...>
- **Disposición**: descartada | en pausa | adoptar en vNext
- **Evidencia**: <links>
```

Reglas:
- El bloque **Estado actual** se reescribe en cada sesión que toca la estrategia; el
  resto es **append-only** (no se edita historia; una corrección es una entrada nueva).
- Las entradas FORMAL son las únicas que mueven `version`/`status`; deben coincidir con
  el `STRATEGY.md` (lo verifica la Pieza 3).
- La cabecera de entrada es semi-estructurada (fecha · version · tipo) para que el
  validador y futuras herramientas la parseen sin ambigüedad.
- **Regla de la versión en la cabecera FORMAL**: siempre termina con la versión
  RESULTANTE tras la entrada. Bump → `### … · v0.1→v0.2 · [FORMAL]`; génesis →
  `### … · v0.1 (génesis) · [FORMAL]`. El validador toma **el último token `vX.Y`**
  de la cabecera como la versión declarada, y la compara con `STRATEGY.md.version`.

## Pieza 2 — La guía: `tournaments/STRATEGY_EVOLUTION.md` + regla de oro

Doc global corto que estandariza el proceso:
- **Cuándo** se agrega cada tipo de entrada (FORMAL en todo cambio de config/status;
  OBSERVACIÓN cuando se prueba/descarta/pausa una idea sin cambiar el config).
- **Ciclo de vida** y evidencia requerida por transición:
  - `draft → under_review`: al menos una OBSERVACIÓN con resultado + una hipótesis de edge.
  - `under_review → approved`: entrada FORMAL que cite un **backtest con edge** (o
    evidencia live equivalente) + sizing definido.
  - `* → deprecated`: entrada FORMAL con la razón del retiro.
- El **template exacto** (copia de la Pieza 1).
- Nueva **regla de oro** en `CLAUDE.md`: *"Toda evolución de una estrategia (cambio de
  params/status o idea probada/descartada) se registra en su `EVOLUTION.md` — ver
  `tournaments/STRATEGY_EVOLUTION.md`."*

## Pieza 3 — El validador: `scripts/check_strategy_evolution.py`

Función pura + CLI, estilo `check_freshness`:
- Para cada estrategia con `STRATEGY.md`: parsea su `version`/`status` (vía el loader
  existente `parse_strategy_md`, salvo las doc-only como `theta_lay_v1`, que se saltean
  por su nota explícita) y la **última entrada FORMAL** de su `EVOLUTION.md`.
- Verifica: (a) existe `EVOLUTION.md`; (b) la última FORMAL declara la misma `version`
  (y status) que el `STRATEGY.md`. Drift → violación (config cambió sin registrar el
  porqué, o al revés).
- Salida texto/`--json`, **exit code ≠ 0** si hay drift. Advisory (para vos/CI), no
  bloquea acciones de runtime.
- Contrato: `StrategyEvolutionCheck(strategy_id, ok, detail, remedy)` (reusa el patrón
  de `PreconditionResult`; puede compartir el schema o uno hermano en `core/schemas/`).

## Bootstrap

Sembrar `EVOLUTION.md` para las estrategias existentes:
- `match_winner_wc_v1` (WC): **best-effort** — reconstruir hitos desde
  `git log -- .../STRATEGY.md`, `STRATEGY_MIGRATION.md` y los findings del WC (migración
  v1.0, documentar `bet_type`, sesgo Poisson knockout, etc.). Genesis + hitos.
- `match_winner_ligamx_v1` (Liga MX): genesis (v0.1 draft) + OBSERVACIÓN "backtest sin
  edge" (2026-07-14) + FORMAL "umbral 0.05→0.10" (2026-07-18, el cambio E3 real).
- `theta_lay_v1` (Liga MX): genesis (v0.1 draft, doc-only) + OBSERVACIÓN de la evidencia
  de concepto del WC (+6.9%…+21.4%) y la validación J1-J3 pendiente.
- `game_winner_v1` (NFL): genesis (v?, approved) desde su `STRATEGY_MIGRATION.md`.

## Errores / edge cases

- `EVOLUTION.md` ausente → el validador lo marca (advisory), no rompe.
- Estrategia doc-only (`theta_lay_v1`, no parseable por el loader): el validador NO
  compara version contra el loader; igual espera `EVOLUTION.md` con entradas.
- Entrada FORMAL malformada (sin `version`) → el validador la reporta como no parseable.

## Testing

- Validador (unit, determinístico, con archivos temporales):
  - STRATEGY.md v0.2 + EVOLUTION última FORMAL v0.2 → ok.
  - STRATEGY.md v0.2 + EVOLUTION última FORMAL v0.1 (o sin FORMAL) → drift.
  - EVOLUTION.md ausente → violación advisory.
  - doc-only strategy → no compara loader, pero exige EVOLUTION.md.
- Parser de entradas FORMAL: extrae `version` de la cabecera `### … · v..→vX · [FORMAL]`.

## Alcance / YAGNI

- Formato Markdown (no JSONL/schema pesado) — el razonamiento es prosa; la estructura
  vive en la cabecera de entrada, suficiente para el validador.
- Validador advisory, sin hard-block en runtime.
- Sin UI/render dedicado (el MD se lee directo); si hiciera falta, se agrega después.

## Archivos afectados

| Archivo | Cambio |
|---|---|
| `tournaments/STRATEGY_EVOLUTION.md` | **nuevo** — la guía/proceso |
| `tournaments/*/strategies/*/EVOLUTION.md` | **nuevos** — un ledger por estrategia (bootstrap) |
| `scripts/check_strategy_evolution.py` | **nuevo** — validador CLI |
| `core/strategy_evolution.py` (+ schema) | **nuevo** — función pura de parseo/validación |
| `tests/unit/test_strategy_evolution.py` | **nuevo** |
| `CLAUDE.md` | nueva regla de oro + puntero a la guía |
