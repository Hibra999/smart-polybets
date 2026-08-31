from __future__ import annotations

from typing import Callable

from research.functions.wc_strategy import pick_side
from signals.base import Signal


class FootballSignalProvider:
    sport = "football"

    def __init__(
        self,
        tournament_id: str,
        strategy,
        predict: Callable | None = None,
        *,
        sport: str = "football",
    ) -> None:
        self.sport = sport
        self._tournament_id = tournament_id
        self._strategy = strategy
        if predict is None:
            from research.functions.model_loader import get_event_prediction
            self._predict: Callable = get_event_prediction
        else:
            self._predict = predict

    def signal(self, home: str, away: str, *, event_id: str | None = None) -> Signal | None:
        prediction = self._predict(event_id, self._tournament_id)
        if prediction is None:
            return None
        pick = pick_side(prediction, self._strategy.side_criterion, self._strategy.blend_weight)
        return Signal(
            model_probability=pick["model_prob"],
            side=pick["side"],
            model_confidence=prediction.model_confidence.value,
            model_version=prediction.model_version,
            sample_size=prediction.sample_size,
        )
