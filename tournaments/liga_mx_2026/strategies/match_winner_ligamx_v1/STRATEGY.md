# STRATEGY: Match Winner — Liga MX Apertura 2026

Borrador clonado de `match_winner_wc_v1` como punto de partida. **NO OPERAR**
hasta: (1) calibrar ventaja de localía (el blend/Elo del WC es neutral-venue),
(2) definir seeds de Elo (hoy: flat 1500, cold start), (3) backtest sobre
jornadas jugadas del Apertura y/o temporadas previas.

## HEADER
version: 0.1
status: draft
author: Claude (scaffolding 2026-07-14) — pendiente de revisión del CIO
last_updated: 2026-07-14

## SCOPE
tournament_id: liga_mx_2026
sport: football
market_type: match_winner
venue: Polymarket
outcomes: [HOME_WIN, AWAY_WIN]

## THESIS
(borrador) **Backtest 2025/26 (2026-07-14): el modelo solo NO le gana al cierre**
(Brier/log-loss peores que el mercado; sim de apuestas ROI -5.3% a +0.6%, ver
docs/findings/2026-07-14-ligamx-backtest.md). El único edge plausible es que
**Polymarket precie peor que el cierre** (mercado nuevo desde 2026-07-13, poca
liquidez) — SIN demostrar. Plan de validación J1-J3: registrar PM vs Poisson vs
cierre (MEX.csv semanal); aprobar solo con evidencia, umbral de edge ≥0.10 y
sizing chico. El yardstick de precio es el **Poisson 1X2 con `neutral=False`**
(el empate es ~25-30% en liga), no el blend win/no-win — lección del Mundial
(docs/findings/2026-07-13-poisson-sesgo-knockout.md).

## SIGNAL DEFINITION
edge_threshold_auto: 0.05
edge_threshold_review: 0.02
edge_threshold_discard: 0.0
min_market_volume_usdc: 500
max_hours_to_event: 168
min_hours_to_event: 1

## RISK LIMITS
max_exposure_per_participant: 0.10
max_open_positions: 8
max_kelly_fraction: 0.25
max_drawdown_7d: 0.15
review_event_phases: [liguilla, final]

## SELECCIÓN DE LADO
bet_type: win
side_criterion: blend
blend_weight: 0.5
warmup_match_no: 3
use_bayes_filter: false
bayes_threshold: 0.5

## SIZING
sizing_method: fractional_kelly
kelly_fraction: 0.25
max_bet_usdc: 25
min_bet_usdc: 5

## QUALITATIVE RULES
- QR-001: Partido entre semana post-fecha FIFA / con rotación anunciada → REVIEW
- QR-002: Lesiones/cambios tácticos reportados en últimas 6h → REVIEW
- QR-003: Altura (CDMX/Toluca/Pachuca) como factor de localía extra → mencionar en reporte

## PERFORMANCE TARGETS
win_rate_target: 0.50
roi_target: 0.10
max_drawdown_allowed: 0.20
evaluation_period: tournament
