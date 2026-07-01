# STRATEGY: Top Scorer (Golden Boot) — FIFA World Cup 2026

## HEADER
version: 0.1
status: draft
author: Guillermo Izquierdo
last_updated: 2026-06-15

## SCOPE
tournament_id: fifa_world_cup_2026
sport: football
market_type: top_scorer
venue: Polymarket
outcomes: [YES, NO]

## THESIS
Mercado de Bota de Oro: el edge proviene de proyectar goles esperados por jugador
(xG acumulado + minutos proyectados según avance del equipo) vs el precio de
Polymarket, que suele anclar en nombres mediáticos por encima de su producción real.

## SIGNAL DEFINITION
edge_threshold_auto: 0.10
edge_threshold_review: 0.05
edge_threshold_discard: 0.05
min_market_volume_usdc: 3000
max_hours_to_event: 168
min_hours_to_event: 2

## RISK LIMITS
max_exposure_per_participant: 0.10
max_open_positions: 8
max_kelly_fraction: 0.04
max_drawdown_7d: 0.20
review_event_phases: [knockout, final]

## SIZING
sizing_method: fractional_kelly
kelly_fraction: 0.20
max_bet_usdc: 40
min_bet_usdc: 5

## QUALITATIVE RULES
- QR-101: Lesión o suspensión del jugador objetivo → DISCARD inmediato
- QR-102: Equipo eliminado (el jugador ya no suma partidos) → reducir size 100%
- QR-103: Cambio de rol táctico (deja de ser titular) → activar REVIEW

## PERFORMANCE TARGETS
win_rate_target: 0.40
roi_target: 0.25
max_drawdown_allowed: 0.30
evaluation_period: tournament
