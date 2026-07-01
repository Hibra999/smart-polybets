"""Narrativa cualitativa de un trade.

La narrativa "rica" la redacta Claude en runtime; esta función produce un esqueleto
determinístico (modo AUTO/REVIEW + por qué) que Claude puede expandir. Siempre
indica si fue AUTO o REVIEW.
"""
from __future__ import annotations

from risk.schemas.risk_verdict import RiskVerdict


def narrate(verdict: RiskVerdict, *, context: str | None = None) -> str:
    opp = verdict.opportunity
    mode = verdict.verdict.value
    reasons = "; ".join(verdict.reasons) if verdict.reasons else "reglas cuantitativas"
    base = (
        f"Trade {mode} sobre {opp.outcome} en {opp.participant_home} vs "
        f"{opp.participant_away}: edge de {float(opp.edge):.1%} con confianza "
        f"{opp.model_confidence}. Clasificado {mode} porque {reasons}."
    )
    if verdict.qualitative_flags:
        base += f" Flags: {', '.join(verdict.qualitative_flags)}."
    if context:
        base += f" {context}"
    return base
