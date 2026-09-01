# SKILL: Research

## ROL EN EL PIPELINE
Producir MarketOpportunity validadas con edge calculado.
Es la primera área del pipeline — nada se ejecuta sin pasar por aquí.

## CUÁNDO INVOCAR
- El humano dice "analiza el partido X" o "busca oportunidades para hoy"
- Se detecta un evento deportivo próximo en las siguientes 24h
- El humano pregunta "¿hay algo interesante en Polymarket?"
- Se inicia el workflow full_analysis o quick_scan

## CUÁNDO NO INVOCAR
- Para verificar el estado del portafolio (eso es portfolio/)
- Para construir una orden (eso es execution/)
- Para calcular PnL de trades ya ejecutados (eso es portfolio/)
- Si no hay torneo activo registrado en `tournaments/registry`

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `model_loader.get_event_prediction()` | Carga probabilidades del modelo del torneo | event_id, tournament_id | MatchPrediction |
| `market_scanner.find_markets()` | Busca mercados en Polymarket para el evento | MatchPrediction, strategy | list[PolymarketMarket] |
| `edge_screener.calculate_edge()` | Calcula edge = p_modelo - p_polymarket | MatchPrediction, PolymarketMarket, strategy | MarketOpportunity |
| `probability_extractor.get_model_prob()` | Extrae probabilidad específica del outcome | MatchPrediction, outcome | Decimal |

## SCHEMAS QUE CONSUME
- `adapters/base.SportAdapter` (vía model_loader → tournaments/registry)
- Cuotas LIVE de Polymarket vía `PolymarketLiveSource` (SDK, `venue/`); `SqliteOddsSource`
  para backtests (fuente inyectable)

## SCHEMAS QUE PRODUCE
- `research/schemas/match_prediction.MatchPrediction`
- `research/schemas/market_opportunity.MarketOpportunity`  ← output principal

## CONSTRAINTS
- NUNCA hardcodear tournament_id — siempre leerlo del registro activo
- NUNCA calcular edge sin verificar que el mercado tiene volumen >= min_market_volume_usdc
- NUNCA producir una MarketOpportunity sin `generated_at` y `strategy_version`
- Si el modelo no tiene predicción para el evento, retornar None — no inventar probabilidad

## EJEMPLO DE USO
```python
prediction = model_loader.get_event_prediction("match_123", "liga_mx_2026")
markets = market_scanner.find_markets(prediction, strategy)
opps = [edge_screener.calculate_edge(prediction, m, strategy) for m in markets]
```

## ERRORES COMUNES
- Confundir condition_id (identifica el market) con event_id (identifica el partido)
- Usar market_probability de un cache en vez del call live al CLOB API
- Generar MarketOpportunity con edge positivo cuando el volumen es < threshold
