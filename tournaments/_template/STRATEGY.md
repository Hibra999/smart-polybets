# STRATEGY: {Nombre descriptivo}

## HEADER
version: 0.1
status: draft
author: {autor}
last_updated: {YYYY-MM-DD}

## SCOPE
tournament_id: {tournament_id}
sport: {sport}
market_type: {market_type}
venue: Polymarket
outcomes: [OUTCOME_A, OUTCOME_B]

## THESIS
[Por qué existe el edge.]

## SIGNAL DEFINITION
edge_threshold_auto: 0.08
edge_threshold_review: 0.04
edge_threshold_discard: 0.04
min_market_volume_usdc: 5000
max_hours_to_event: 24
min_hours_to_event: 1

## RISK LIMITS
max_exposure_per_participant: 0.15
max_open_positions: 10
max_kelly_fraction: 0.05
max_drawdown_7d: 0.20
review_event_phases: [playoff, knockout, final]

## SIZING
sizing_method: fractional_kelly
kelly_fraction: 0.25
max_bet_usdc: 50
min_bet_usdc: 5

## QUALITATIVE RULES
- QR-001: {descripción} → {acción}

## PERFORMANCE TARGETS
win_rate_target: 0.55
roi_target: 0.15
max_drawdown_allowed: 0.25
evaluation_period: tournament
