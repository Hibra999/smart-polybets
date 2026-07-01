"""Tipos base compartidos por todas las áreas.

Son los enums y aliases que forman el vocabulario común del sistema. Se definen
aquí una sola vez para que no haya divergencia entre áreas (single source of truth).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import NewType

# ── Aliases semánticos ───────────────────────────────────────────────────────
Timestamp = datetime
Money = Decimal  # siempre USDC en este sistema
WalletAddress = NewType("WalletAddress", str)
TournamentId = NewType("TournamentId", str)
ConditionId = NewType("ConditionId", str)  # identificador de mercado en Polymarket
TokenId = NewType("TokenId", str)          # identificador de token YES/NO en Polymarket
EventId = NewType("EventId", str)          # identificador de partido en el repo del torneo


class SportType(str, Enum):
    """Deportes soportados. Determina qué schema DDL y qué adapter aplican."""

    FOOTBALL = "football"
    AMERICAN_FOOTBALL = "american_football"
    BASKETBALL = "basketball"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class ModelConfidence(str, Enum):
    """Confianza del modelo según el tamaño de muestra histórico."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class VerdictType(str, Enum):
    """Veredicto del área de Risk sobre una oportunidad."""

    AUTO = "AUTO"
    REVIEW = "REVIEW"
    DISCARD = "DISCARD"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class DecisionStatus(str, Enum):
    """Estados de un AgentDecisionLog en el Django App."""

    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"
    DISCARDED = "discarded"


# Outcomes genéricos de Polymarket (un mercado binario YES/NO).
OUTCOME_YES = "YES"
OUTCOME_NO = "NO"
