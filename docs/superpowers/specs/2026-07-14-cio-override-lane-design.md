# Diseño: Carril CIO-override (apuestas manuales por el pipeline)

**Fecha**: 2026-07-14 · **Aprobado por**: CIO (opción B) · **Estado**: aprobado

## Problema
Las apuestas que la estrategia activa no puede generar (lado Poisson en mercados a 90',
totales O/U, sizing aprobado por el CIO distinto al Kelly-blend) se colocan hoy por
scripts manuales (`place_totals_qf.py`, `place_winner_sf.py`) que bypassean el motor de
riesgo, la idempotencia y el ledger (`LocalState`). Ya hay 7 operaciones live sin traza
en el ledger (5 totales + 2 semifinales). El ledger miente (0 trades) y la traza vive en
findings escritos a mano.

## Decisión
Un carril **CIO-override** dentro del framework: la apuesta manual se convierte en una
**Decision real** que pasa por riesgo → REVIEW forzado → aprobación tipeada → ledger.

### Componentes
1. **`agent/tools/override_tools.py`** (nuevo)
   - `propose_override(opp, stake_usdc, reason, client, strategy) -> dict`:
     idempotencia → `risk.evaluate()` con la estrategia activa (límites reales:
     edge/volumen/drawdown/horas/exposure) → si DISCARD, se bloquea (no se guarda) →
     si pasa, RiskVerdict **forzado a REVIEW** (un override nunca es AUTO) con
     `recommended_size_usdc = stake` del CIO y `reasons += "CIO override: <reason>"`
     → `ExecutionDecision` → `save_decision` (status `pending_approval`).
   - `strategy_id = "cio_override"`, `strategy_version = "1.0"` en la opportunity →
     idempotency key estándar (`hash(condition_id+outcome+strategy_id+version+date)`).
2. **`scripts/propose_bet.py`** (nuevo, CLI)
   - `--market "<question>"` (match exacto o substring único contra mercados abiertos
     vía `venue.discovery`), `--outcome yes|no`, `--stake N`, `--model-prob P`,
     `--reason "..."`. Construye la `MarketOpportunity` (best_ask live, tick, min size,
     kickoff, volumen) y llama `propose_override`. Imprime la key y el siguiente paso.
3. **Colocación**: la existente — `orders.py --approve <key> --live --confirm <monto>`
   (reprecia al best_ask, valida slippage/evento, confirmación tipeada, y
   `mark_executed` SOLO si el fill es live). Sin cambios.
4. **`scripts/backfill_manual_trades.py`** (nuevo, one-off idempotente)
   - Retro-registra las 7 operaciones manuales ya hechas como decisiones `executed`
     con `strategy_id="manual_override"`, `backfill: true` y sus fills reales
     (condition_id/precio/stake de la cuenta live + findings). Re-ejecutable sin duplicar.

### Higiene (bugs documentados en CLAUDE.md)
5. **`place_bets.py` no llama `load_env()`** → se agrega (paridad con `orders.py`).
6. **Dry-run marcaba `status=executed`** (`full_analysis.py`): ahora
   `mark_executed` solo con `result.status == "live"`; un dry-run marca el nuevo status
   **`simulated`** (método aditivo `LocalStateClient.mark_simulated`) y la idempotencia
   permite reprocesar decisiones `simulated`/`expired` (un dry-run ya no bloquea el
   run real siguiente). Test de integración actualizado (codificaba el bug).

## Flujo resultante
```
CIO: propose_bet.py --market … --stake … --reason …
  → risk.evaluate (puede DISCARDear: edge<0, volumen, drawdown, horas, exposure)
  → Decision REVIEW en LocalState (pending_approval, key idempotente)
CIO: orders.py --approve <key> --live --confirm <monto>
  → reprecia, valida, confirmación tipeada → broker → mark_executed (solo live)
```
El escape hatch de broker directo sigue existiendo para emergencias, pero deja de ser
la ruta normal; si se usa, anotar en findings (como hasta ahora).

## No-objetivos (siguiente iteración)
- `match_winner_wc_v2` con `side_criterion: poisson` (elimina la necesidad del override
  para el caso común; requiere backtest). Queda para NFL 2026 / próximo torneo.
- Importación automática de posiciones live al ledger en `account.py --reconcile`.

## Tests
- `tests/unit/test_override_tools.py`: fuerza REVIEW, respeta stake CIO, DISCARD
  bloquea sin guardar, segunda llamada misma-key → SKIP idempotente.
- `tests/integration/test_full_analysis.py`: AUTO en dry-run → `simulated` (no
  `executed`), re-run permitido; AUTO live → `executed`.
