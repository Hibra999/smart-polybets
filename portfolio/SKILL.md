# SKILL: Portfolio

## ROL EN EL PIPELINE
Es el custodio del estado local del agente (`LocalState`, `core/local_state.py`) y el
puente hacia la cuenta LIVE de Polymarket (vía `venue/gateway`, ver `account_source.py`).
Lee estado del portafolio, persiste decisiones del agente, y calcula métricas de
performance. (Django fue retirado; el estado vive en `data/agent_state.json`.)

## CUÁNDO INVOCAR
- Siempre al inicio del pipeline (para leer portfolio_state)
- Para verificar idempotencia antes de procesar cualquier oportunidad
- Para persistir el resultado de cada etapa del pipeline
- El humano pregunta "¿cómo voy?" o "¿cuál es mi PnL?"
  → **Fuente de verdad = cuenta LIVE, no el ledger local** (suele estar desincronizado en 0).
    Correr `python scripts/account.py --closed 300 --json` y reportar **equity total = cash +
    Σ(shares × current_price de abiertas)** (el balance es solo cash, no suma posiciones), las
    posiciones abiertas y el histórico ganado/perdido con record W-L y neto. Ver `CLAUDE.md` §
    "Reportar PnL / cuenta".

## CUÁNDO NO INVOCAR
- Para construir órdenes (eso es execution/)
- Para generar reportes narrativos (eso es editorial/)

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `position_tracker.get_state()` | Lee estado completo del portafolio | LocalStateClient | PortfolioState |
| `position_tracker.get_exposure()` | Exposición por participante | LocalStateClient, tournament_id | dict |
| `pnl_calculator.realized_pnl()` | PnL realizado acumulado | list[Trade] | Decimal |
| `pnl_calculator.unrealized_pnl()` | PnL no realizado de posiciones abiertas | list[Position] | Decimal |
| `performance_metrics.summary()` | Métricas completas de performance | PortfolioState, trades | PerformanceSummary |
| `position_tracker.check_idempotency()` | Verifica si una key ya existe | LocalStateClient, idempotency_key | dict \| None |
| `position_tracker.save_decision()` | Persiste un AgentDecisionLog | LocalStateClient, ExecutionDecision | dict |
| `position_tracker.mark_executed()` | Marca un log como ejecutado (solo fills `live`) | LocalStateClient, key, OrderResult | dict |
| `position_tracker.mark_simulated()` | Registra un dry-run (`simulated`, NO bloquea idempotencia) | LocalStateClient, key, OrderResult | dict |
| `account_source.PolymarketAccountSource` | Cuenta LIVE (saldo/posiciones/órdenes) | venue/gateway | snapshots live |

## SCHEMAS QUE CONSUME
- `execution/schemas/execution_decision.ExecutionDecision`
- `execution/schemas/order_result.OrderResult`

## SCHEMAS QUE PRODUCE
- `portfolio/schemas/portfolio_state.PortfolioState`  ← consumido por risk/ y optimization/
- `portfolio/schemas/performance_summary.PerformanceSummary`

## CONSTRAINTS
- NUNCA cachear PortfolioState entre steps del pipeline — siempre lectura fresca
- NUNCA escribir directamente al JSON de estado — siempre a través de LocalStateClient
- check_idempotency() es OBLIGATORIO antes de save_decision() — sin excepciones
- Si el estado local no se puede leer/escribir, el workflow PARA — no continúa con estado stale
- ⚠️ Para PnL usar SIEMPRE la cuenta live (ver CUÁNDO INVOCAR arriba). Desde 2026-07-14
  el ledger sí registra las apuestas manuales (carril CIO override `propose_bet.py` +
  backfill `backfill_manual_trades.py`), pero la valuación/resolución sigue viniendo
  de la cuenta live.
- Los status del ledger: `pending_approval` (REVIEW), `approved`, `executed` (fill live),
  `simulated` (dry-run; NO bloquea idempotencia), `expired`.

## ERRORES COMUNES
- Leer portfolio_state una sola vez y usarlo para todo el pipeline (queda stale)
- No hacer check_idempotency() por "estar seguros de que es nueva" — siempre verificar
