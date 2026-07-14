"""Tests de localía (Elo/pipeline), seeds flat consistentes y venue/results.

Cubre lo agregado el 2026-07-14 para Liga MX:
  - EloSystem.home_adv: sube P(local) y se aplica en updates (default 0 = WC intacto)
  - seeds flat 1500 → TrueSkill y Bayes arrancan uniformes (cold start coherente)
  - reconstrucción de marcador: Exact Score (Liga MX) y escalera O/U (Mundial)
"""
from __future__ import annotations

from types import SimpleNamespace

from adapters.football.wc_models import BayesianLeague, EloSystem
from adapters.football.wc_pipeline import WorldCupPipeline
from adapters.football.wc_trueskill import TrueSkillSystem
from venue.results import reconstruct_score, score_from_exact_markets, score_from_ou_ladder


# ── localía ──────────────────────────────────────────────────────────────────

def test_home_adv_raises_home_expectation():
    neutral = EloSystem()
    con_adv = EloSystem(home_adv=65.0)
    for e in (neutral, con_adv):
        e.seed({"a": 1500.0, "b": 1500.0})
    assert neutral.expected_home("a", "b") == 0.5
    assert con_adv.expected_home("a", "b") > 0.55  # 65 pts ≈ 59%


def test_home_adv_zero_keeps_worldcup_behavior():
    e = EloSystem()
    e.seed({"a": 1600.0, "b": 1500.0})
    before = (e.get("a"), e.get("b"))
    e.update_match("a", "b", 2, 0)
    # sin localía el update es el clásico; sólo verificamos que movió en la
    # dirección esperada y que home_adv default es 0
    assert e.home_adv == 0.0
    assert e.get("a") > before[0]


def test_pipeline_passes_home_adv_to_elo():
    pipe = WorldCupPipeline(home_adv_elo=65.0)
    pipe.seed({"a": 1500.0, "b": 1500.0})
    snap = pipe.prematch("a", "b")
    assert snap["p_home"] > 0.55
    neutral = WorldCupPipeline()
    neutral.seed({"a": 1500.0, "b": 1500.0})
    assert neutral.prematch("a", "b")["p_home"] == 0.5


# ── cold start coherente (Elo flat → TS/Bayes flat) ─────────────────────────

def test_flat_elo_seed_gives_flat_trueskill_and_bayes():
    flat = {t: 1500.0 for t in ("a", "b", "c", "d")}
    ts = TrueSkillSystem()
    ts.seed_from_elo(flat)
    mus = {r.mu for r in ts.ratings.values()}
    assert len(mus) == 1  # todos el mismo mu (25.0)
    bay = BayesianLeague()
    bay.seed_from_elo(flat)
    means = {round(bay.get(t).mean, 9) for t in flat}
    assert means == {0.5}


# ── venue/results ────────────────────────────────────────────────────────────

def _mk(question: str, resolved: str | None):
    yes = SimpleNamespace(price=(0.999 if resolved == "yes" else 0.001)
                          if resolved else None, label="Yes")
    no = SimpleNamespace(price=(0.999 if resolved == "no" else 0.001)
                         if resolved else None, label="No")
    # para O/U los labels son Over/Under
    if resolved in ("over", "under"):
        yes = SimpleNamespace(price=0.999 if resolved == "over" else 0.001, label="Over")
        no = SimpleNamespace(price=0.999 if resolved == "under" else 0.001, label="Under")
    return SimpleNamespace(question=question, outcomes=SimpleNamespace(yes=yes, no=no))


def test_exact_score_direct():
    mkts = [
        _mk("Exact Score: Club Necaxa 0 - 0 Atlante FC?", None),
        _mk("Exact Score: Club Necaxa 2 - 1 Atlante FC?", "yes"),
        _mk("Exact Score: Club Necaxa 1 - 1 Atlante FC?", "no"),
    ]
    assert score_from_exact_markets(mkts, "Club Necaxa", "Atlante FC") == (2, 1)
    # y con los nombres canónicos del proyecto (aliases de matching)
    assert reconstruct_score(mkts, "Necaxa", "Atlante") == (2, 1)


def test_ou_ladder_worldcup_format():
    mkts = [
        _mk("France vs. Morocco: France O/U 0.5", "over"),
        _mk("France vs. Morocco: France O/U 1.5", "over"),
        _mk("France vs. Morocco: France O/U 2.5", "under"),
        _mk("France vs. Morocco: Morocco O/U 0.5", "under"),
        _mk("France vs. Morocco: O/U 2.5", "under"),
        _mk("France vs. Morocco: O/U 1.5", "over"),
    ]
    assert score_from_ou_ladder(mkts, "France", "Morocco") == (2, 0)


def test_reconstruct_prefers_exact_score():
    mkts = [
        _mk("Exact Score: Necaxa 3 - 2 Atlante?", "yes"),
        _mk("Necaxa vs. Atlante: Necaxa O/U 0.5", "under"),  # escalera contradictoria
    ]
    assert reconstruct_score(mkts, "Necaxa", "Atlante") == (3, 2)
