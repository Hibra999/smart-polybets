# STRATEGY: Match Winner (blend + Kelly) — FIFA World Cup 2026

Estrategia **migrada** desde `pypro_worldcup_betting` (estrategia activa en
`worldcup.db`: *"kelly + blend + filtro no"*, backtest yield 21.8% / ROI 19.0%).
Ver `STRATEGY_MIGRATION.md` para el mapeo completo origen → framework.

## HEADER
version: 1.0
status: approved
author: Guillermo Izquierdo (migrado de pypro_worldcup_betting)
last_updated: 2026-06-20

## SCOPE
tournament_id: fifa_world_cup_2026
sport: football
market_type: match_winner            # mercado binario al ganador (YES por lado)
venue: Polymarket
outcomes: [HOME_WIN, AWAY_WIN]        # sin DRAW: el modelo worldcup es win/no-win

## THESIS
El lado se elige con el ensemble Elo+Bayes (blend 50/50) evolucionado partido a
partido desde la semilla FIFA→Elo. El edge proviene de que el modelo, calibrado
con resultados reales del torneo, diverge del precio implícito de Polymarket. El
sizing es Kelly fraccional (¼) sobre la cuota del mercado. No se usa filtro Bayes.

## SIGNAL DEFINITION
# Sin gate de edge explícito (como el origen): se apuesta cualquier edge positivo;
# el Kelly se encarga de no apostar cuando el modelo no supera el break-even.
edge_threshold_auto: 0.02
edge_threshold_review: 0.0
edge_threshold_discard: 0.0
min_market_volume_usdc: 1000
max_hours_to_event: 168
min_hours_to_event: 1

## RISK LIMITS
max_exposure_per_participant: 0.15
max_open_positions: 12
max_kelly_fraction: 0.25            # no topar el Kelly migrado (¼ de Kelly puro)
max_drawdown_7d: 0.20
review_event_phases: [knockout, final]

## SELECCIÓN DE LADO (migrado de betting.BetParams)
side_criterion: blend              # elo | bayes | blend | trueskill
blend_weight: 0.5                  # peso de Elo en 'blend' (1-w para Bayes)
warmup_match_no: 2                 # start_match_no: arranca en la 2ª aparición del lado
use_bayes_filter: false
bayes_threshold: 0.5

## SIZING
sizing_method: fractional_kelly
kelly_fraction: 0.25
max_bet_usdc: 50
min_bet_usdc: 5

## QUALITATIVE RULES
- QR-001: Partido meaningless (ambos equipos ya clasificados/eliminados) → reducir size 50%
- QR-002: Lesiones/cambios tácticos reportados en últimas 6h → activar REVIEW
- QR-003: Clima extremo que afecte el modelo → mencionar en reporte

## PERFORMANCE TARGETS
win_rate_target: 0.50
roi_target: 0.19                   # ROI logrado en backtest worldcup
max_drawdown_allowed: 0.25
evaluation_period: tournament
