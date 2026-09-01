# STRATEGY: Theta Lay — lay del favorito con salida anticipada (Liga MX)

Estrategia de TRADING (no bet-and-hold): comprar el NO del favorito al kickoff
en mercados "Will X win" (resuelven a 90') y salir vendiendo antes de la
resolución. Monetiza (a) el decaimiento temporal del favorito mientras el
partido siga cerrado y (b) el sobreprecio retail del favorito (sesgo
favorito-longshot, finding 2026-07-14-ligamx-sesgos-mercado).

La hipótesis todavía no está validada con ticks, spread y fees propios de Liga MX.
Por eso permanece en `draft` y no puede operar en AUTO.

> ⚠️ **Doc-only — NO se carga vía `parse_strategy_md`/`load_active_strategy`.**
> Es una estrategia de trading intradía dirigida a mano por el CIO (`review_required:
> true`), operada por CLI (`theta_monitor.py`), no por el pipeline de decisión. Por eso
> su `## SIGNAL DEFINITION` usa campos propios del theta (`min_fav_yes`,
> `entry_window_min`, …) y **no** los campos que exige `StrategyConfig`
> (`edge_threshold_*`, `max/min_hours_to_event`): esos son irrelevantes para un lay
> intradía. Cargar este archivo con el loader canónico fallaría a propósito.

## HEADER
version: 0.1
status: draft
author: CIO + Codex (2026-07-14)
last_updated: 2026-07-14

## SCOPE
tournament_id: liga_mx_2026
sport: football
market_type: match_winner            # se opera el token NO del favorito
venue: Polymarket
outcomes: [NO_FAVORITO]

## THESIS
El favorito en mercados a 90' está estructuralmente caro en venues retail
(empate ~25-30% en liga + flujo recreativo compra favoritos). Al kickoff se
compra su NO; cada minuto sin gol del favorito el NO gana valor. La salida
anticipada evita el riesgo de resolución y captura el theta. El edge NO
presupone un venue blando y disciplina de salida; ambas condiciones deben medirse
antes de aprobar la estrategia.

## SIGNAL DEFINITION
# Entrada: favorito = lado con mayor precio Yes 5min pre-kickoff
min_fav_yes: 0.40                    # sin favorito claro no hay trade
min_market_volume_usdc: 200          # liquidez mínima del mercado
entry_window_min: 5                  # entrar entre kickoff-5min y kickoff+5min

## EXIT RULES (execution/functions/theta_exit.py — pura, testeada)
tp_pct: 0.05                         # take-profit BRUTO sobre costo (calibrar neto con ticks J1)
from_min: 30                         # el TP aplica desde este minuto wall-clock
hard_exit_min: 105                   # venta forzada (≈ min 85 de juego), pase lo que pase
stop_pct: none                       # sin stop por default (los goles gapean; el sizing es el stop)

## RISK LIMITS
max_stake_per_trade_usdc: 10         # sizing chico por riesgo de gol temprano
max_concurrent_trades: 2
max_exposure_theta_usdc: 30          # tope total simultáneo de la estrategia
review_required: true                # cada trade lo arma el CIO a mano (CLI), no hay AUTO

## EJECUCIÓN (manual vía CLI — ver docs/theta-trade-manual.md)
- Entrada: carril CIO override (`propose_bet.py --outcome no` + `orders.py --approve`).
- Salida: `scripts/theta_monitor.py` (regla automática + hard stop manual `v`).
- Registro: sesiones/ticks en `theta_session`/`theta_tick`; la entrada queda en el
  ledger mediante el carril CIO.
- El guard de frescura MONEY bloquea `propose_bet.py`/`orders.py` ante datos viejos
  salvo un `--force --reason` autorizado.

## VALIDACIÓN PENDIENTE (bloquea pasar a approved)
1. J1-J3 Liga MX con sizing de prueba (≤$10): medir PnL NETO de fees y spread real.
2. Ticks propios del recorder → backtest ejecutable de Liga MX.
3. Calibrar tp_pct neto y from_min con esa data.
4. **EDA de goles 2025/26** (finding 2026-07-14-ligamx-goles-eda): el entorno es
   hostil para este trade (3.10 goles/partido; favorito ya anotó
   antes del min 30 en 37%; bin 76-90 es el más denso; rojas en 34% de partidos,
   mediana min 74). Hipótesis a testear con ticks J1-J3 ANTES de aprobar:
   `hard_exit_min` 60-75 (no 105), `from_min` 20-25, y regla de rojas
   (salir si roja al dog / aguantar si roja al favorito). Los defaults actuales
   son provisionales.

## PERFORMANCE TARGETS
win_rate_target: 0.60
roi_target: 0.08                     # neto de fees, por trade
max_drawdown_allowed: 0.15
evaluation_period: J1-J6 Apertura 2026
