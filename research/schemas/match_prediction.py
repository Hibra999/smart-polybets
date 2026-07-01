"""MatchPrediction — output del modelo del torneo (consumido internamente por research)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.types import ModelConfidence


class MatchPrediction(BaseModel):
    """Probabilidades de un evento producidas por el ensemble del repo del torneo.

    `probabilities` mapea outcome del modelo -> probabilidad. Las claves son
    específicas del mercado (ej: HOME_WIN/DRAW/AWAY_WIN para match_winner).
    """

    model_config = ConfigDict(frozen=True)

    event_id: str
    tournament_id: str
    sport: str
    market_type: str

    participant_home: str
    participant_away: str
    event_start_utc: datetime
    event_phase: str

    probabilities: dict[str, Decimal] = Field(default_factory=dict)

    # Componentes por modelo para estrategias multi-criterio (migración worldcup):
    # {"elo": {"HOME_WIN": .., "AWAY_WIN": ..}, "bayes": {...}, "trueskill": {...}}
    components: dict[str, dict[str, Decimal]] = Field(default_factory=dict)
    # Nº de aparición de cada participante (para reglas de warmup como start_match_no).
    appearances: dict[str, int] = Field(default_factory=dict)

    model_version: str
    model_confidence: ModelConfidence
    sample_size: int

    generated_at: datetime

    @field_validator("probabilities")
    @classmethod
    def _probs_in_range(cls, v: dict[str, Decimal]) -> dict[str, Decimal]:
        for outcome, p in v.items():
            if not (Decimal("0") <= p <= Decimal("1")):
                raise ValueError(f"Probabilidad fuera de [0,1] para {outcome!r}: {p}")
        return v

    def prob_for(self, outcome: str) -> Decimal | None:
        """Probabilidad del modelo para un outcome, o None si no la predijo."""
        return self.probabilities.get(outcome)
