"""Construcción de reportes en Markdown. Funciones puras (+ guardado en disco).

NUNCA incluye credenciales ni wallet addresses completas. Los reportes se guardan
en editorial/reports/{tournament_id}/ con fecha en el nombre.
"""
from __future__ import annotations

import os
from pathlib import Path

from core.utils import date_str
from execution.schemas.execution_decision import ExecutionDecision
from execution.schemas.order_result import OrderResult
from risk.schemas.risk_verdict import RiskVerdict

REPORTS_ROOT = Path(os.getenv("REPORTS_ROOT", "editorial/reports"))


def build_review_report(decision: ExecutionDecision) -> str:
    """Reporte estructurado de un REVIEW pendiente (formato de agent/AGENTS.md)."""
    v = decision.verdict
    opp = v.opportunity
    flags = "\n  ".join(v.qualitative_flags) if v.qualitative_flags else "(ninguno)"
    reasons = "; ".join(v.reasons) if v.reasons else "(sin razones)"
    deadline = decision.approval_deadline.isoformat() if decision.approval_deadline else "—"

    return f"""---
TRADE REVIEW REQUEST
idempotency_key: {decision.idempotency_key}
deadline: {deadline}

OPORTUNIDAD
  Partido: {opp.participant_home} vs {opp.participant_away}
  Mercado: {opp.outcome} ({opp.market_type})
  Fase: {opp.event_phase}
  Kickoff: {opp.event_start_utc.isoformat()}

PROBABILIDADES
  Modelo: {float(opp.model_probability):.1%}
  Polymarket: {float(opp.market_probability):.1%}
  Edge: {float(opp.edge):.1%}
  Confianza modelo: {opp.model_confidence} (n={opp.sample_size} partidos)

SIZING
  Kelly recomendado: {decision.size_usdc} USDC
  Razón de REVIEW (no AUTO): {reasons}

FLAGS CUALITATIVOS
  {flags}

RECOMENDACIÓN DEL AGENTE
  [Codex escribe aquí 2-3 líneas de análisis cualitativo]

ACCIONES
  [ ] APROBAR — responde "aprobar {decision.idempotency_key}"
  [ ] RECHAZAR — responde "rechazar {decision.idempotency_key} [razón]"
  [ ] MODIFICAR TAMAÑO — responde "modificar {decision.idempotency_key} size={{monto}}"
---
"""


def build_execution_summary(order_result: OrderResult, verdict: RiskVerdict) -> str:
    """Resumen Markdown de una ejecución completada."""
    opp = verdict.opportunity
    return f"""## Ejecución — {opp.participant_home} vs {opp.participant_away}

- **Mercado:** {opp.outcome} ({opp.market_type})
- **Modo:** {verdict.verdict.value}
- **Edge entrada:** {float(opp.edge):.1%}
- **Tamaño:** {order_result.filled_size_usdc} USDC
- **Precio promedio:** {order_result.avg_price}
- **Order ID:** `{order_result.order_id}`
- **Status:** {order_result.status}
"""


def save_report(tournament_id: str, content: str, *, suffix: str = "report",
                ext: str = "md", root: Path | None = None,
                date: str | None = None) -> Path:
    """Guarda un reporte en reports/{tournament_id}/YYYY-MM-DD_{suffix}.{ext}."""
    base = root or REPORTS_ROOT
    out_dir = base / tournament_id
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{date or date_str()}_{suffix}.{ext}"
    path.write_text(content, encoding="utf-8")
    return path
