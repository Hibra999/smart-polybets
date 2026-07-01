"""Extracción de la probabilidad del modelo para un outcome específico."""
from __future__ import annotations

from decimal import Decimal

from research.schemas.match_prediction import MatchPrediction


def get_model_prob(prediction: MatchPrediction, model_outcome: str) -> Decimal | None:
    """Probabilidad del modelo para `model_outcome` (ej: HOME_WIN), o None."""
    return prediction.prob_for(model_outcome)
