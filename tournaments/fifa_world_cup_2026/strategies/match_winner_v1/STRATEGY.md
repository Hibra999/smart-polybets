# STRATEGY: Match Winner — FIFA World Cup 2026

## HEADER (parseado por el agente — campos obligatorios)
version: 0.1
status: approved
author: Guillermo Izquierdo
last_updated: 2026-06-15

## SCOPE
tournament_id: fifa_world_cup_2026   # debe existir en tournaments/registry.py
sport: football
market_type: match_winner            # tipo de mercado de Polymarket que cubre
venue: Polymarket
outcomes: [HOME_WIN, DRAW, AWAY_WIN]

## THESIS
El edge proviene de la divergencia entre el ensemble Elo/Bayes del repo de modelos
y el precio implícito de Polymarket, especialmente en partidos de fase de grupos
donde el mercado sobre-reacciona a narrativas mediáticas. El modelo es más estable
que el sentimiento del mercado en las primeras jornadas.

---

## SIGNAL DEFINITION

### Fuentes de probabilidad
- model_probability: output del ensemble del repo vinculado
- market_probability: midpoint del token YES en Polymarket CLOB API
- edge: model_probability - market_probability

### Thresholds de decisión (parseados como StrategyConfig)
edge_threshold_auto: 0.08
edge_threshold_review: 0.04
edge_threshold_discard: 0.04
min_market_volume_usdc: 5000
max_hours_to_event: 24
min_hours_to_event: 1

## RISK LIMITS
# Límites de riesgo explícitos (extensión canónica para parseo limpio)
max_exposure_per_participant: 0.15
max_open_positions: 10
max_kelly_fraction: 0.05
max_drawdown_7d: 0.20
review_event_phases: [playoff, knockout, final]

---

## ENTRY RULES

### AUTO (todas deben cumplirse — evaluación determinística)
- edge >= edge_threshold_auto
- market_volume >= min_market_volume_usdc
- hours_to_event entre min_hours_to_event y max_hours_to_event
- exposición proyectada por equipo < max_exposure_per_participant
- posiciones abiertas < max_open_positions
- kelly_fraction <= max_kelly_fraction

### REVIEW (cualquiera activa modo REVIEW — requiere aprobación humana)
- edge entre edge_threshold_review y edge_threshold_auto
- event_phase en [playoff, knockout, final]
- model_confidence == LOW
- qualitative_flag_count > 0

### DISCARD (cualquiera descarta sin aprobación posible)
- edge < edge_threshold_discard
- market_volume < min_market_volume_usdc
- drawdown_7d > max_drawdown_7d
- hours_to_event < min_hours_to_event

---

## EXIT RULES

### Cierre automático
- Resolución del mercado (Polymarket cierra el mercado)
- Stop-loss por posición: pérdida unrealizada > 60% del valor inicial

### Cierre en REVIEW
- Precio cae a < 0.15 en posición YES comprada

---

## SIZING
sizing_method: fractional_kelly
kelly_fraction: 0.25
max_bet_usdc: 50
min_bet_usdc: 5

---

## QUALITATIVE RULES
# Formato: QR-{ID}: {descripción} → {acción si aplica}
- QR-001: Si el partido es meaningless (ambos equipos ya clasificados/eliminados) → reducir size 50%
- QR-002: Reportes de cambios tácticos o lesiones en últimas 6h → activar REVIEW
- QR-003: Condiciones climáticas extremas que afecten el modelo → mencionar en reporte

---

## PERFORMANCE TARGETS
win_rate_target: 0.55
roi_target: 0.15
max_drawdown_allowed: 0.25
evaluation_period: tournament
