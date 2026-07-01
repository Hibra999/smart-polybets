# SKILL: Editorial

## ROL EN EL PIPELINE
Última área del pipeline. Convierte datos estructurados de las otras áreas
en reportes legibles: resúmenes de análisis, narrativas de trades, y digests
de performance. NO toma decisiones de trading.

## CUÁNDO INVOCAR
- Para generar el reporte de un REVIEW que espera aprobación
- Después de que resuelve un mercado (post_event_review workflow)
- El humano pide "dame un resumen de la semana" o "¿cómo estuvo el torneo?"
- Después de un batch de ejecuciones para documentar lo que pasó

## CUÁNDO NO INVOCAR
- En el camino crítico de una ejecución urgente (primero ejecuta, luego reporta)
- Para tomar decisiones de trading (solo narra, no decide)

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `report_builder.build_review_report()` | Reporte estructurado para un REVIEW pendiente | ExecutionDecision | str (Markdown) |
| `report_builder.build_execution_summary()` | Resumen de una ejecución completada | OrderResult, RiskVerdict | str (Markdown) |
| `report_builder.save_report()` | Guarda un reporte en reports/{tournament_id}/ | tournament_id, content | Path |
| `trade_narrator.narrate()` | Narrativa cualitativa de un trade | RiskVerdict, context | str |
| `performance_digest.weekly()` | Digest semanal completo | tournament_id, period, decisions | WeeklyDigest |
| `performance_digest.tournament_final()` | Reporte final del torneo | tournament_id, period, decisions | WeeklyDigest |

## SCHEMAS QUE CONSUME
- `execution/schemas/execution_decision.ExecutionDecision`
- `execution/schemas/order_result.OrderResult`
- `portfolio/schemas/performance_summary.PerformanceSummary`

## SCHEMAS QUE PRODUCE
- `editorial/schemas/trade_report.TradeReport`
- `editorial/schemas/weekly_digest.WeeklyDigest`
- Archivos Markdown en `editorial/reports/{tournament_id}/`

## CONSTRAINTS
- NUNCA publicar automáticamente — todo queda en editorial/reports/ para revisión manual
- Los reportes son SIEMPRE en Markdown, guardados con fecha en el nombre
- NUNCA incluir credenciales, wallet addresses completas, o claves privadas en reportes
- La narrativa de trade_narrator debe indicar si fue AUTO o REVIEW (y por qué)

## ERRORES COMUNES
- Generar el reporte REVIEW antes de que risk/ haya calculado el kelly_fraction
- Omitir los qualitative_flags del RiskVerdict en el reporte
- Guardar el reporte sin tournament_id en el path (rompe la organización por torneo)
