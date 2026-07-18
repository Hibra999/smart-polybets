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
- Archivos Markdown o HTML en `editorial/reports/{tournament_id}/` (o `_system/` cross-torneo)

## CONSTRAINTS
- NUNCA publicar automáticamente — todo queda en editorial/reports/ para revisión manual
- **TODO reporte vive en `editorial/reports/{tournament_id}/`** (o `_system/` si es
  cross-torneo), con **fecha en el nombre**: `YYYY-MM-DD_<slug>.{md,html}`. NUNCA en `docs/`.
- Formato: Markdown **o** HTML (las funciones ya generan ambos: `html_report.py`,
  `backtest_html.py`, `poisson_report.py`). Lo no negociable es el path por torneo + la fecha.
- **`docs/` es SOLO para docs del sistema** (manuales, arquitectura, explicación de modelos):
  documentación que no caduca con los datos de un evento. Si el entregable responde
  "¿cómo fue X evento/semana/torneo?" o caduca al cambiar los datos → es REPORTE → va aquí,
  no en `docs/`. Ver `docs/findings/2026-07-17-docs-vs-editorial-reports.md`.
- NUNCA incluir credenciales, wallet addresses completas, o claves privadas en reportes
- La narrativa de trade_narrator debe indicar si fue AUTO o REVIEW (y por qué)

## ERRORES COMUNES
- Generar el reporte REVIEW antes de que risk/ haya calculado el kelly_fraction
- Omitir los qualitative_flags del RiskVerdict en el reporte
- Guardar el reporte sin tournament_id en el path (rompe la organización por torneo)
