# SKILL: Optimization

## ROL EN EL PIPELINE
Dado un RiskVerdict con Kelly calculado, refina el tamaño de la apuesta
aplicando constraints del portafolio completo (cvxpy, opcional). Garantiza que
el sizing sea óptimo en el contexto de todas las posiciones abiertas.

## CUÁNDO INVOCAR
- Después de risk/ cuando el verdict es AUTO o REVIEW
- El humano pregunta "¿cómo distribuyo el capital entre estas apuestas?"
- Se necesita optimizar un batch de oportunidades simultáneas

## CUÁNDO NO INVOCAR
- Antes de tener un RiskVerdict (no puede correr sin él)
- Si el verdict es DISCARD (no hay nada que optimizar)
- Para calibrar thresholds históricos (eso es threshold_calibrator, tarea separada)

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `bet_sizer.size_single()` | Sizing de una apuesta (cap max_bet, SKIP si < min_bet) | RiskVerdict, strategy | SizingOutput |
| `portfolio_optimizer.optimize_batch()` | cvxpy: max EV para un batch | list[RiskVerdict], PortfolioState, strategy | OptimizationResult |
| `threshold_calibrator.backtest_thresholds()` | Calibra edge_threshold_auto por backtesting | historical_trades | dict |

## SCHEMAS QUE CONSUME
- `risk/schemas/risk_verdict.RiskVerdict`
- `portfolio/schemas/portfolio_state.PortfolioState`

## SCHEMAS QUE PRODUCE
- `optimization/schemas/sizing_output.SizingOutput`
- `optimization/schemas/optimization_result.OptimizationResult`

## CONSTRAINTS
- El sizing NUNCA puede superar max_bet_usdc del STRATEGY.md
- El sizing NUNCA puede ser menor a min_bet_usdc (si es así, retornar SKIP)
- NUNCA modificar el verdict (AUTO/REVIEW/DISCARD) — solo el tamaño
- Si cvxpy no converge (o no está instalado), usar Kelly fraccional simple como fallback

## NOTA DE ORDENAMIENTO
El whitepaper §2.2 dibuja Research → Optimization → Risk, pero los SKILL.md (más
detallados) ubican Optimization DESPUÉS de Risk: Risk calcula el Kelly base y
Optimization lo refina con el contexto del portafolio. Los workflows siguen este
orden: Research → Risk → Optimization → Execution.
