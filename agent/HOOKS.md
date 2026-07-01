# HOOKS.md — Registro de Triggers del Agente

## QUÉ ES UN HOOK
Un hook es la condición de entrada que determina qué workflow o área debe
activarse dado el input del operador. Claude Code los lee para mapear lenguaje
natural a acciones del sistema. NO son eventos automáticos — Claude se lanza
manualmente y mapea la intención al hook correcto.

## TABLA DE HOOKS

| Hook ID | Trigger (lenguaje natural) | Área/Workflow | Modo |
|---|---|---|---|
| H-001 | "analiza el partido X" / "evalúa el evento X" | full_analysis workflow | PIPELINE |
| H-002 | "busca oportunidades" / "¿qué hay para hoy?" | quick_scan workflow | PIPELINE |
| H-003 | "nuevo torneo: {id}" / "registra el torneo X" | django_sync_tools.register_tournament | WRITE |
| H-004 | "¿cómo voy?" / "dame el PnL" / "estado del portafolio" | portfolio_tools.performance_summary | READ |
| H-005 | "post-partido" / "revisa el resultado de X" | post_event_review workflow | PIPELINE |
| H-006 | "aprobar {key}" | django_sync_tools.mark_approved | WRITE |
| H-007 | "rechazar {key} [razón]" | django_sync_tools.mark_rejected | WRITE |
| H-008 | "modificar {key} size={monto}" | django_sync_tools + re-run execution/ | WRITE |
| H-009 | "resumen de la semana" / "digest semanal" | editorial.performance_digest.weekly | READ |
| H-010 | "calibra los thresholds" | optimization.threshold_calibrator | COMPUTE |
| H-011 | "nueva estrategia para {torneo}" | research/notebooks/ → draft mode | DRAFT |
| H-012 | "¿qué estrategia está activa?" | tournaments/registry.load_active_strategy | READ |

## MODOS DE EJECUCIÓN

**PIPELINE:** Research → Risk → Optimization → Execution → Portfolio
- Lee el SKILL.md de cada área antes de invocarla
- Verifica idempotencia en portfolio/ al inicio
- Termina en Editorial si hay algo que reportar

**READ:** Solo lectura — consulta el Django App o los archivos del repo. No escribe estado.

**WRITE:** Escribe estado en el Django App. Confirma con el humano si es irreversible.

**COMPUTE:** Cálculos pesados (backtesting, optimización). No escribe a producción sin aprobación.

**DRAFT:** Modo experimental. Todo va a notebooks/ o a strategies con status: draft.
NUNCA activa workflows aprobados en modo DRAFT.

## REGLAS DE MAPEO
1. Si el input contiene un event_id o nombre de partido → H-001 (full_analysis)
2. Si el input es una pregunta sobre el estado → H-004 (portfolio read)
3. Si el input contiene "aprobar/rechazar/modificar" + una key → H-006/H-007/H-008
4. Si el input menciona "torneo" + "nuevo/registra" → H-003
5. Si ningún hook mapea claramente → Claude pregunta al humano antes de actuar
6. Si hay ambigüedad entre H-001 y H-002 → preferir H-002 (menos destructivo)

## HOOK CHAINS (secuencias automáticas)
- H-001 → si hay REVIEW pendiente → Editorial genera reporte de REVIEW
- H-006 (aprobar) → execution/ → submit_order() → H-005 (post_event al resolver)
- H-005 → Editorial → guarda reporte en editorial/reports/{tournament_id}/

## REGLA DE ORO
Claude Code NUNCA ejecuta un hook WRITE o PIPELINE sin leer primero:
1. agent/CLAUDE.md (reglas de operación generales)
2. El SKILL.md del área que va a invocar
3. El STRATEGY.md activo del torneo en curso
