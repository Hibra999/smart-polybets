# STRATEGY: Game Winner (TrueSkill + Kelly) — NFL 2026

Estrategia **migrada** de `sports_bet` (modelo TrueSkill + sizing Kelly). El lado se
elige por el rating TrueSkill (probabilidad de victoria); el edge se mide contra el
moneyline implícito de Polymarket. Ver `STRATEGY_MIGRATION.md`.

## HEADER
version: 1.0
status: approved
author: Guillermo Izquierdo (migrado de sports_bet)
last_updated: 2026-06-20

## SCOPE
tournament_id: nfl_2026
sport: american_football
market_type: game_winner
venue: Polymarket
outcomes: [HOME_WIN, AWAY_WIN]        # mercado binario (sin empate práctico en NFL)

## THESIS
El rating TrueSkill (N(μ,σ²)) se actualiza juego a juego con los resultados reales
desde 2022. La probabilidad de victoria sale de la receta TrueSkill
P = Φ((μ_A−μ_B)/√(2β²+σ²)). El edge proviene de la divergencia con el moneyline de
Polymarket, especialmente en equipos que el mercado tarda en re-evaluar.

## SIGNAL DEFINITION
# Sin gate de edge explícito (se apuesta cualquier edge positivo; el Kelly regula).
edge_threshold_auto: 0.05
edge_threshold_review: 0.0
edge_threshold_discard: 0.0
min_market_volume_usdc: 5000
max_hours_to_event: 168
min_hours_to_event: 1

## RISK LIMITS
max_exposure_per_participant: 0.12
max_open_positions: 16
max_kelly_fraction: 0.25
max_drawdown_7d: 0.20
review_event_phases: [wildcard, divisional, conference, superbowl]

## SELECCIÓN DE LADO (migrado de sports_bet)
side_criterion: trueskill           # rating TrueSkill por equipo
blend_weight: 0.5
warmup_match_no: 4                   # arranca tras ~4 juegos (ratings estables)
use_bayes_filter: false
bayes_threshold: 0.5

## SIZING
sizing_method: fractional_kelly
kelly_fraction: 0.25
max_bet_usdc: 60
min_bet_usdc: 5

## QUALITATIVE RULES
- QR-201: QB titular con game_status Out/Doubtful en el injury report → activar REVIEW
- QR-202: Clima extremo en estadio sin domo (viento >25mph, nieve) → mencionar en reporte
- QR-203: Partido sin implicaciones de playoffs (semana 18, descanso de titulares) → reducir size 50%

## PERFORMANCE TARGETS
win_rate_target: 0.53
roi_target: 0.10
max_drawdown_allowed: 0.22
evaluation_period: season
