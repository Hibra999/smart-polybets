# SKILL: Risk

## ROL EN EL PIPELINE
Recibe MarketOpportunity, aplica las reglas del STRATEGY.md activo,
y emite un RiskVerdict (AUTO / REVIEW / DISCARD) con sizing recomendado.
Es el guardián — nada llega a Execution sin pasar por aquí.

## CUÁNDO INVOCAR
- Siempre después de research/, antes de execution/
- El humano pregunta "¿es buena esta apuesta?" o "¿cuánto debo apostar?"
- Se necesita verificar si el portafolio tiene espacio para una posición nueva

## CUÁNDO NO INVOCAR
- Para analizar trades ya ejecutados (eso es portfolio/)
- Para construir la orden técnica (eso es execution/)
- Si no existe un MarketOpportunity validado de research/

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `kelly.fractional_kelly()` | Calcula tamaño óptimo fraccional | win_prob, price, fraction, bankroll | KellyOutput |
| `exposure.check_participant_exposure()` | Verifica límite de exposición por equipo | portfolio_state, participant, size, threshold | bool |
| `drawdown.check_portfolio_stop_loss()` | Verifica si el drawdown supera el límite | portfolio_state, max_drawdown | bool |
| `correlation.estimate_correlation()` | Estima correlación con posiciones abiertas | opportunity, open_positions | float |
| `evaluate()` | Función maestra: aplica todas las reglas del STRATEGY.md | MarketOpportunity, StrategyConfig, PortfolioState | RiskVerdict |

## SCHEMAS QUE CONSUME
- `research/schemas/market_opportunity.MarketOpportunity`
- `portfolio/schemas/portfolio_state.PortfolioState` (vía django_client)
- `core/strategy.StrategyConfig` (STRATEGY.md parseado)

## SCHEMAS QUE PRODUCE
- `risk/schemas/risk_verdict.RiskVerdict`  ← output principal
- `risk/schemas/kelly_output.KellyOutput`

## CONSTRAINTS
- NUNCA emitir AUTO si alguna regla DISCARD aplica, aunque sea una sola
- NUNCA calcular Kelly sin leer primero el portfolio_state live del Django App
- NUNCA hardcodear thresholds — siempre leerlos del STRATEGY.md activo
- NUNCA emitir RiskVerdict sin listar las razones en el campo `reasons`
- Si hay flags cualitativos (QR-XXX), SIEMPRE incluirlos en `qualitative_flags`

## ERRORES COMUNES
- Leer el portfolio_state de un cache stale — siempre hacer GET fresco
- Emitir REVIEW cuando todas las reglas AUTO se cumplen (demasiado conservador)
- No incluir los QR flags cuando aplican — el humano los necesita para decidir
