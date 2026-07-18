# STRATEGY: Theta Lay — lay del favorito con salida anticipada (Liga MX)

Estrategia de TRADING (no bet-and-hold): comprar el NO del favorito al kickoff
en mercados "Will X win" (resuelven a 90') y salir vendiendo antes de la
resolución. Monetiza (a) el decaimiento temporal del favorito mientras el
partido siga cerrado y (b) el sobreprecio retail del favorito (sesgo
favorito-longshot, finding 2026-07-14-ligamx-sesgos-mercado).

Evidencia de concepto: 26 KO del WC 2026 con price history real de PM →
+6.9% (salida 30min) a +21.4% (105min) BRUTO, 16W-10L a 90min
(finding 2026-07-14-theta-trade-lay-favorito). NO validado aún en Liga MX.

## HEADER
version: 0.1
status: draft
author: CIO + Claude (2026-07-14)
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
requiere modelo (demostrado: los features no agregan info sobre el precio) —
requiere venue blando + disciplina de salida.

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
max_stake_per_trade_usdc: 10         # sizing chico: la cola es -0.46/share (gol temprano)
max_concurrent_trades: 2
max_exposure_theta_usdc: 30          # tope total simultáneo de la estrategia
review_required: true                # cada trade lo arma el CIO a mano (CLI), no hay AUTO

## EJECUCIÓN (manual vía CLI — ver docs/theta-trade-manual.md)
- Entrada: carril CIO override (`propose_bet.py --outcome no` + `orders.py --approve`).
- Salida: `scripts/theta_monitor.py` (regla automática + hard stop manual `v`).
- Registro: sesiones/ticks en `theta_session`/`theta_tick`; asentar el round-trip
  en el ledger con `backfill_manual_trades.py`.
- ⚠️ **Guard de frescura mandatorio (tier MONEY)**: `propose_bet.py`/`orders.py` se
  bloquean ante datos viejos salvo `--force --reason`. Diseño:
  `docs/superpowers/specs/2026-07-17-mandatory-dependency-hooks-design.md`.

## VALIDACIÓN PENDIENTE (bloquea pasar a approved)
1. J1-J3 Liga MX con sizing de prueba (≤$10): medir PnL NETO de fees y spread real.
2. Ticks propios (recorder) → replicar el backtest WC sobre Liga MX ejecutable.
3. Calibrar tp_pct neto y from_min con esa data.
4. ⚠️ **EDA de goles 2025/26** (finding 2026-07-14-ligamx-goles-eda): Liga MX es
   MÁS hostil que el WC para este trade (3.10 goles/partido; favorito ya anotó
   antes del min 30 en 37%; bin 76-90 es el más denso; rojas en 34% de partidos,
   mediana min 74). Hipótesis a testear con ticks J1-J3 ANTES de aprobar:
   `hard_exit_min` 60-75 (no 105), `from_min` 20-25, y regla de rojas
   (salir si roja al dog / aguantar si roja al favorito). Los defaults actuales
   heredan del WC y probablemente NO son óptimos acá.

## PERFORMANCE TARGETS
win_rate_target: 0.60                # el backtest WC dio 16/26 a 90min
roi_target: 0.08                     # neto de fees, por trade
max_drawdown_allowed: 0.15
evaluation_period: J1-J6 Apertura 2026
