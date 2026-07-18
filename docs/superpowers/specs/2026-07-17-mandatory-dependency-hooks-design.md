# Diseño — Validaciones mandatorias de dependencias (precondiciones + hooks)

**Fecha:** 2026-07-17
**Estado:** aprobado (brainstorming) — pendiente plan de implementación

## Problema

El protocolo de sesión (CLAUDE.md) manda **refrescar los datos antes de cualquier
sugerencia o apuesta** (los modelos reproducen los fixtures jugados en runtime → DB
vieja = edges falsos). Hoy eso vive **solo como prosa**: el agente lo olvida y los
scripts pueden correrse con datos viejos sin que nadie avise. Caso real: se pidió el
PnL / una sugerencia con la DB del torneo desactualizada y el resultado fue engañoso.

Queremos convertir esas dependencias en **validaciones mandatorias enforced**, no en
un recordatorio que se puede saltar.

## Decisiones tomadas (brainstorming)

1. **Enforcement híbrido** (defensa en profundidad): un módulo puro de checks como
   fuente de verdad, del que cuelgan guards en código + un Claude Code hook.
2. **Comportamiento escalonado por nivel de acción**: dinero → hard-block; lectura/
   análisis → aviso fuerte y sigue.
3. **Solo hook `SessionStart`** (simple y suficiente): sin `PreToolUse`.
4. **`placeholders_synced` es advisory** (nunca bloquea; requiere red).

## Principio rector aplicado

Reproducibilidad: mismas entradas → misma evaluación. Las precondiciones son
**funciones puras** sobre estado local (SQLite read-only + env), con contratos
Pydantic. Ningún threshold ni comportamiento hardcodeado fuera de este módulo.

## Sección 1 — Catálogo de precondiciones (el corazón)

Módulo nuevo `core/preconditions.py`: predicados puros que devuelven un
`PreconditionResult`. Es la **única fuente de verdad** de "qué está fresco".

| ID | Severidad | Qué verifica | Señal (local salvo nota) | Remedio (comando) |
|---|---|---|---|---|
| `fixtures_finalized` | mandatory | No hay fixtures jugados sin finalizar | `status='scheduled' AND kickoff_utc < now` excluyendo partidos in-play ahora (mismo query que `update_results.py:76`) | `python scripts/update_results.py --tournament <tid> --apply` |
| `live_gates_ready` | mandatory (solo tier MONEY) | key + `POLYMARKET_LIVE=1` + kill-switch off | env + estado local | setear env / desactivar kill-switch |
| `placeholders_synced` | advisory | Placeholders de bracket (`elo_rating NULL`) con kickoff próximo aún sin mapear | requiere red (PM) → puede quedar `unknown` | `python scripts/sync_upcoming_fixtures.py --apply` (WC) / `fetch_fixtures_pm.py --apply` (Liga MX) |

**Torneos activos:** se iteran desde `tournaments.registry.TOURNAMENTS`, filtrando por
ventana de fechas (`start_date <= hoy <= end_date`). La ruta de la DB por torneo se
resuelve reutilizando la convención/helper existente que ya usa `update_results.py`
(no se hardcodea acá, para no duplicar).

**Contrato (`core/schemas/precondition.py`, Pydantic frozen):**
```
PreconditionResult:
    name: str                     # "fixtures_finalized"
    ok: bool | None               # True=cumple, False=violación, None=no verificable
    severity: Literal["mandatory","advisory"]
    tournament_id: str | None
    detail: str                   # human-readable ("3 fixtures jugados sin finalizar")
    remedy_cmd: str | None        # comando exacto de remedio
```
Todo lo que se imprime (guards, CLI, hook) sale de este objeto → un solo formato.

## Sección 2 — Capas de enforcement

**Capa 0 — Orquestador:**
- `core/preconditions.py::evaluate(tier, tournaments=None) -> list[PreconditionResult]`
  corre las precondiciones que aplican al tier. Puro.
- `scripts/check_freshness.py`: CLI fino (texto o `--json`) que imprime resultados y
  **sale con exit code ≠ 0 si hay alguna violación `mandatory` con `ok is False`**.
  Reutilizable por humano, cron y hook.

**Capa 1 — Guards en las acciones** (helper `core/preconditions.py::enforce`):

| Acción | Tier | Precondiciones | Comportamiento si viola |
|---|---|---|---|
| `account.py`, `scan_market.py` | READ/ANALYSIS | `fixtures_finalized` (+advisory) | **AVISA** (imprime violación + remedio) y **procede** |
| `propose_bet.py`, `place_bets.py`, `orders.py` | MONEY | `fixtures_finalized`, `live_gates_ready` | **HARD-BLOCK** (exit ≠ 0) salvo `--force` con `--reason` |

`enforce(tier, *, tournaments=None, force=False, reason=None)` al inicio de cada
script: evalúa, imprime, y bloquea o avisa según tier. En tier MONEY, `--force` sin
`--reason` → error de input; el `--force` usado queda registrado (consistente con el
carril CIO override).

**Alcance por torneo (evita bloqueos cruzados):** una acción de dinero sobre un mercado
concreto bloquea solo si **su** torneo está viejo — el guard recibe el `tournament_id`
de la acción cuando es determinable (`propose_bet`/`place_bets`/`orders` ya lo conocen o
lo derivan del mercado). Si no se puede determinar, cae a "todos los activos". Las
lecturas transversales (`account.py` = PnL de toda la cuenta) sí evalúan **todos** los
torneos activos.

**Capa 2 — Claude Code hook** (`.claude/settings.json`, nuevo):
- **`SessionStart`** ejecuta `python scripts/check_freshness.py`; su salida se inyecta
  al contexto → cada sesión arranca sabiendo si hay datos viejos. Best-effort: si el
  CLI falla, imprime nota y no aborta la sesión.

## Sección 3 — Data flow, errores, testing

**Data flow:**
```
TOURNAMENTS (registry, filtro por fecha)
      → evaluate(tier, tournaments): por torneo abre data/<tid>/<tid>.sqlite (RO)
        → predicados puros → [PreconditionResult]
          ├─ enforce()            (guards en acción: bloquea/avisa por tier)
          ├─ check_freshness.py   (CLI + exit code)
          └─ SessionStart hook    (inyecta aviso al agente)
```

**Errores:**
- DB inexistente o precondición no verificable (red caída para la advisory) → `ok=None`
  (`unknown`), **nunca rompe** la acción: degrada a aviso. Solo `mandatory` + `ok is False`
  bloquea.
- Hook `SessionStart` best-effort (nunca aborta la sesión).
- Tier MONEY con `--force` sin `--reason` → error de input (fuerza a justificar).

**Testing (unit, determinístico):**
- Predicados: SQLite temporal — fila `scheduled` con kickoff pasado → violación; sin
  ella → ok; partido in-play ahora → NO cuenta como violación.
- `evaluate()`: mezcla de torneos; filtra por tier.
- `enforce()`: MONEY bloquea (exit≠0) sin force; con `--force --reason` procede y
  registra; READ avisa y procede.
- `check_freshness.py`: exit 0 / ≠0 según haya violación mandatoria.

## Alcance / YAGNI

- **No se toca** la lógica de las acciones ni de los scripts de update.
- Se agrega: módulo puro + schema, CLI `check_freshness.py`, helper `enforce()` (una
  línea al inicio de cada script de la tabla), y `.claude/settings.json` con `SessionStart`.
- `placeholders_synced` entra como advisory (no bloquea nunca).
- Sin `PreToolUse`, sin auto-remediación, sin checks basados en tiempo ("DB no tocada en
  N horas") — la señal `scheduled + kickoff pasado` es más robusta que un timestamp.

## Archivos afectados

| Archivo | Cambio |
|---|---|
| `core/schemas/precondition.py` | **nuevo** — `PreconditionResult` |
| `core/preconditions.py` | **nuevo** — predicados puros, `evaluate()`, `enforce()` |
| `scripts/check_freshness.py` | **nuevo** — CLI + exit code |
| `.claude/settings.json` | **nuevo** — hook `SessionStart` |
| `scripts/account.py`, `scan_market.py` | +1 línea: `enforce("READ", ...)` |
| `scripts/propose_bet.py`, `place_bets.py`, `orders.py` | +`--force/--reason` + `enforce("MONEY", ...)` |
| `tests/unit/test_preconditions.py` | **nuevo** — predicados, evaluate, enforce, CLI |
| `CLAUDE.md` | nota: el protocolo de frescura ahora está enforced (apunta a este spec) |
