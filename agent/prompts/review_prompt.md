# PROMPT: Redacción de REVIEW

Un trade fue clasificado REVIEW y requiere aprobación humana.

Usá `editorial.report_builder.build_review_report(decision)` para el esqueleto y
completá la sección **RECOMENDACIÓN DEL AGENTE** con 2-3 líneas de análisis
cualitativo, considerando:
- Los `qualitative_flags` del RiskVerdict (QR-XXX) — explicá su impacto.
- La confianza del modelo y el tamaño de muestra.
- El contexto de la fase del torneo.

No tomes la decisión por el humano: presentá el caso de forma balanceada y dejá
las acciones (APROBAR / RECHAZAR / MODIFICAR) explícitas con la idempotency_key.
Nunca incluyas credenciales ni la wallet completa.
