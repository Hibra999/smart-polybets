"""Estrategia worldcup migrada — selección de lado + warmup + filtro Bayes.

Portado fiel de `pypro_worldcup_betting/app/src/betting.py::pick_side` al diseño
agéntico. La selección de lado usa los componentes por modelo del MatchPrediction
(elo/bayes) y la `side_criterion` del STRATEGY.md. El sizing (Kelly fraccional)
lo aplica el pipeline normal (risk.evaluate → optimization.size_single), porque la
`model_probability` de la oportunidad se fija a la prob Elo del lado elegido — igual
que el `p_pick` del origen.

Características migradas:
  - side_criterion: elo | bayes | blend | trueskill (trueskill degrada a elo)
  - blend_weight: peso de Elo en 'blend'
  - warmup_match_no: salta hasta la N-ésima aparición del lado (start_match_no)
  - use_bayes_filter + bayes_threshold: descarta si la media Bayes < umbral
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from core.strategy import StrategyConfig
from research.functions.edge_screener import calculate_edge
from research.functions.market_scanner import PolymarketMarket
from research.schemas.market_opportunity import MarketOpportunity
from research.schemas.match_prediction import MatchPrediction

HOME_WIN = "HOME_WIN"
AWAY_WIN = "AWAY_WIN"


def pick_side(prediction: MatchPrediction, side_criterion: str,
              blend_weight: Decimal) -> dict:
    """Elige el lado (HOME_WIN/AWAY_WIN) según el criterio. Mirror de betting.pick_side.

    Devuelve {side, model_prob, p_elo, bayes_pick, appearance_no}.
    `model_prob` = prob Elo del lado (el p_pick que usa el Kelly del origen).
    """
    elo = prediction.components.get("elo", prediction.probabilities)
    bayes = prediction.components.get("bayes", {})
    ts = prediction.components.get("trueskill", elo)  # fallback a Elo (como el origen)

    elo_home, elo_away = elo.get(HOME_WIN, Decimal("0.5")), elo.get(AWAY_WIN, Decimal("0.5"))
    bayes_home, bayes_away = bayes.get(HOME_WIN, elo_home), bayes.get(AWAY_WIN, elo_away)
    ts_home, ts_away = ts.get(HOME_WIN, elo_home), ts.get(AWAY_WIN, elo_away)
    w = blend_weight

    if side_criterion == "bayes":
        home_score, away_score = bayes_home, bayes_away
    elif side_criterion == "trueskill":
        home_score, away_score = ts_home, ts_away
    elif side_criterion == "blend":
        home_score = w * elo_home + (Decimal("1") - w) * bayes_home
        away_score = w * elo_away + (Decimal("1") - w) * bayes_away
    else:  # 'elo'
        home_score, away_score = elo_home, elo_away

    # p_pick para el sizing: TrueSkill usa su prob; el resto usa Elo (intacto).
    ph = ts_home if side_criterion == "trueskill" else elo_home
    pa = ts_away if side_criterion == "trueskill" else elo_away

    if home_score >= away_score:
        return {"side": HOME_WIN, "model_prob": ph, "p_elo": elo_home,
                "bayes_pick": bayes_home, "appearance_no": prediction.appearances.get(HOME_WIN, 1)}
    return {"side": AWAY_WIN, "model_prob": pa, "p_elo": elo_away,
            "bayes_pick": bayes_away, "appearance_no": prediction.appearances.get(AWAY_WIN, 1)}


def build_worldcup_opportunity(
    prediction: MatchPrediction,
    markets: list[PolymarketMarket],
    strategy: StrategyConfig,
    *,
    now: datetime | None = None,
) -> MarketOpportunity | None:
    """Construye la oportunidad para el ÚNICO lado que elige la estrategia.

    Devuelve None si el warmup o el filtro Bayes lo descartan, o si no hay mercado
    para el lado elegido.
    """
    pick = pick_side(prediction, strategy.side_criterion, strategy.blend_weight)

    # Warmup (start_match_no): saltar hasta la N-ésima aparición del lado.
    if pick["appearance_no"] < strategy.warmup_match_no:
        return None

    # Filtro Bayes opcional.
    if strategy.use_bayes_filter and pick["bayes_pick"] < strategy.bayes_threshold:
        return None

    market = next((m for m in markets if m.model_outcome == pick["side"]), None)
    if market is None:
        return None

    # model_probability = p_pick del criterio (Elo para elo/bayes/blend; TrueSkill
    # para trueskill). Mismo número que usa el Kelly del origen → sizing fiel.
    return calculate_edge(
        prediction, market, strategy, now=now, model_probability=pick["model_prob"]
    )
