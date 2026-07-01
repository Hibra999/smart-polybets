# PROMPT: Digest de Performance (H-009 / H-005)

Generá un digest de performance del período solicitado.

1. Reuní las decisiones del período (desde el Django App o el input).
2. Computá los números con `editorial.performance_digest.weekly(...)`.
3. Expandí la narrativa:
   - `performance_narrative`: qué pasó y por qué (1 párrafo).
   - `lessons_learned`: bullets accionables.
   - `next_week_outlook`: qué vigilar.
4. Guardá el reporte con `editorial.report_builder.save_report(tournament_id, content)`.

Reglas:
- Sólo Markdown, con fecha en el nombre, dentro de `editorial/reports/{tournament_id}/`.
- Nunca publiques automáticamente: el operador decide qué difundir.
- Nunca incluyas claves, tokens ni wallet addresses completas.
