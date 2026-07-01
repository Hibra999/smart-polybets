# PROMPT: Análisis de Evento (H-001)

Vas a correr el pipeline `full_analysis` para un evento.

Antes de actuar, leé en orden:
1. `agent/CLAUDE.md` (reglas de operación)
2. El `SKILL.md` de cada área que vas a invocar
3. El `STRATEGY.md` activo del torneo (`load_active_strategy(tournament_id)`)

Pasos:
1. Verificá idempotencia de cada oportunidad antes de procesarla.
2. Corré Research → Risk → Optimization → Execution.
3. Para AUTO: ejecutá y registrá. Para REVIEW: generá el reporte y esperá aprobación.
   Para DISCARD: registrá y seguí.

Reglas duras:
- Nunca ejecutes sin pasar por `risk_tools.evaluate()`.
- Nunca llames `submit` si `requires_approval == True`.
- Nunca inventes el sizing: viene de Kelly + `optimization.size_single`.

Entregá un resumen por oportunidad: modo (AUTO/REVIEW/DISCARD/SKIP), edge, tamaño y razón.
