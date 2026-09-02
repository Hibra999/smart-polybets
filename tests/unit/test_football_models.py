"""Tests de modelos de fuerza, pipeline y estrategia de Liga MX."""
from decimal import Decimal

import pytest

from adapters.football.db_reader import FootballDBReader
from adapters.football.model_adapter import FootballModelAdapter
from adapters.football.model_pipeline import FootballModelPipeline
from adapters.football.strength_models import (
    BayesianLeague,
    EloSystem,
    elo_to_prior,
    expected_score,
    match_scores,
)
from research.functions.market_scanner import PolymarketMarket
from research.functions.strategy_selection import build_strategy_opportunity, pick_side
from research.schemas.match_prediction import MatchPrediction
from tournaments.registry import load_active_strategy

STRATEGY = load_active_strategy("liga_mx_2026", require_approved=False)


# ── Modelos (fidelidad de las fórmulas portadas) ─────────────────────────────


def test_expected_score_symmetry():
    assert expected_score(1500, 1500) == 0.5
    assert expected_score(1900, 1500) > 0.9          # 400 pts ≈ 10:1
    assert round(expected_score(1900, 1500) + expected_score(1500, 1900), 9) == 1.0


def test_match_scores():
    assert match_scores(2, 0) == (1.0, 0.0)
    assert match_scores(1, 1) == (0.5, 0.5)
    assert match_scores(0, 3) == (0.0, 1.0)


def test_elo_to_prior_bias():
    a_strong, b_strong = elo_to_prior(1900)
    assert a_strong > b_strong                            # equipo fuerte → prior a ganar


def test_elo_update_moves_toward_winner():
    elo = EloSystem(k=40, use_margin=False)
    elo.seed({"A": 1500, "B": 1500})
    elo.update_match("A", "B", 1, 0)
    assert elo.get("A") > 1500 > elo.get("B")


def test_bayes_update_draw_is_half():
    league = BayesianLeague()
    league.seed_from_elo({"A": 1500, "B": 1500})
    before = league.get("A").mean
    league.update_match("A", "B", 1, 1)                   # empate = 0.5 éxito
    assert league.get("A").mean == pytest.approx(before, abs=0.15)


# ── Pipeline ─────────────────────────────────────────────────────────────────


def test_pipeline_evolves_and_counts_appearances():
    pipe = FootballModelPipeline()
    pipe.seed({"A": 1600, "B": 1500, "C": 1400})
    pipe.process_all([("A", "C", 3, 0)])                  # A golea a C
    snap = pipe.prematch("A", "B")
    assert snap["p_home"] > snap["p_away"]                # A subió, favorito vs B
    assert sum(snap[key] for key in ("p_home", "p_draw", "p_away")) == pytest.approx(1)
    assert snap["home_match_no"] == 2                     # A ya jugó 1 → próxima es la 2ª
    assert snap["away_match_no"] == 1                     # B no ha jugado


# ── Adapter sobre datos seeded ───────────────────────────────────────────────


def test_football_adapter_components(football_conn):
    # football_conn no tiene partidos jugados → predicción sólo desde la semilla.
    reader = FootballDBReader("liga_mx_2026", connection=football_conn)
    pred = FootballModelAdapter("liga_mx_2026", reader=reader).get_event_prediction("m1")
    assert pred is not None
    assert "elo" in pred.components and "bayes" in pred.components
    assert sum(pred.components["elo"].values()) == Decimal(1)
    assert pred.appearances["HOME_WIN"] == 1             # sin partidos jugados
    # Elo: AME(2100) favorito sin ventaja de localía (modelo neutral)
    assert pred.components["elo"]["HOME_WIN"] > Decimal("0.5")


# ── Estrategia: pick_side, blend, warmup, filtro Bayes ───────────────────────


def _prediction(elo_home="0.45", elo_away="0.55", bayes_home="0.70", bayes_away="0.40",
                app_home=3, app_away=3) -> MatchPrediction:
    from core.types import ModelConfidence
    from core.utils import utcnow

    return MatchPrediction(
        event_id="m1", tournament_id="liga_mx_2026", sport="football",
        market_type="match_winner", participant_home="AME", participant_away="CAZ",
        event_start_utc=utcnow(), event_phase="group",
        probabilities={"HOME_WIN": Decimal(elo_home), "AWAY_WIN": Decimal(elo_away)},
        components={
            "elo": {"HOME_WIN": Decimal(elo_home), "AWAY_WIN": Decimal(elo_away)},
            "bayes": {"HOME_WIN": Decimal(bayes_home), "AWAY_WIN": Decimal(bayes_away)},
        },
        appearances={"HOME_WIN": app_home, "AWAY_WIN": app_away},
        model_version="football", model_confidence=ModelConfidence.MEDIUM, sample_size=2,
        generated_at=utcnow(),
    )


def test_pick_side_elo_vs_blend():
    # Elo favorece AWAY (0.55) pero Bayes favorece HOME (0.70 vs 0.40).
    pred = _prediction()
    elo_pick = pick_side(pred, "elo", Decimal("0.5"))
    assert elo_pick["side"] == "AWAY_WIN"
    # blend 50/50: home=0.5*0.45+0.5*0.70=0.575 ; away=0.5*0.55+0.5*0.40=0.475 → HOME
    blend_pick = pick_side(pred, "blend", Decimal("0.5"))
    assert blend_pick["side"] == "HOME_WIN"
    # p_pick (sizing) usa la prob Elo del lado elegido, no el score blend
    assert blend_pick["model_prob"] == Decimal("0.45")


def _market(outcome="HOME_WIN", prob="0.30"):
    return PolymarketMarket(
        condition_id="c", token_id="t", outcome="YES", model_outcome=outcome,
        market_probability=Decimal(prob), volume_usdc=Decimal(6000),
        liquidity_usdc=Decimal(8000),
    )


def test_warmup_skips_first_appearance():
    pred = _prediction(app_home=2)        # debajo del warmup de Liga MX
    # blend elige HOME; warmup_match_no=3 → debe saltar
    opp = build_strategy_opportunity(pred, [_market("HOME_WIN")], STRATEGY)
    assert opp is None


def test_bayes_filter_skips_below_threshold():
    strat = STRATEGY.model_copy(update={"use_bayes_filter": True,
                                        "bayes_threshold": Decimal("0.9")})
    pred = _prediction()                  # bayes_home 0.70 < 0.9
    assert build_strategy_opportunity(pred, [_market("HOME_WIN")], strat) is None


def test_build_opportunity_blend_picks_home():
    pred = _prediction()
    opp = build_strategy_opportunity(pred, [_market("HOME_WIN", "0.30")], STRATEGY)
    assert opp is not None
    assert opp.outcome == "YES"
    # edge = p_elo(home)=0.45 - market 0.30 = 0.15
    assert opp.edge == Decimal("0.15")
    assert opp.strategy_id == "match_winner_ligamx_v1"
