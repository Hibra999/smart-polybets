"""Tests del modelo Poisson de goles (adapters.football.poisson). Puros."""
import math

from adapters.football.poisson import PoissonGoalsModel, poisson_pmf

# Liga de juguete: A es ofensivo y fuerte, C débil. Suficientes partidos para que
# el shrinkage no aplaste todo al promedio.
MATCHES = [
    ("a", "b", 3, 1), ("a", "c", 4, 0), ("b", "c", 2, 1),
    ("c", "a", 0, 3), ("b", "a", 1, 2), ("c", "b", 1, 2),
    ("a", "b", 2, 2), ("c", "a", 1, 4), ("b", "c", 3, 0), ("a", "c", 2, 0),
]


def test_poisson_pmf_matches_formula():
    assert abs(poisson_pmf(2.0, 0) - math.exp(-2.0)) < 1e-12
    # suma de la pmf ~ 1 sobre un soporte amplio
    assert abs(sum(poisson_pmf(1.7, k) for k in range(40)) - 1.0) < 1e-9


def test_pmf_zero_lambda():
    assert poisson_pmf(0.0, 0) == 1.0
    assert poisson_pmf(0.0, 3) == 0.0


def test_fit_sets_base_and_rates():
    m = PoissonGoalsModel(shrink_k=2.0).fit(MATCHES)
    assert m.fitted
    total = sum(hg + ag for _, _, hg, ag in MATCHES)
    assert abs(m.base - total / (2 * len(MATCHES))) < 1e-9
    # A anota mucho mas que C: mayor ataque, mejor defensa (menor 'defense')
    assert m.team("a").attack > m.team("c").attack
    assert m.team("a").defense < m.team("c").defense


def test_unknown_team_is_league_average():
    m = PoissonGoalsModel().fit(MATCHES)
    r = m.team("zzz")
    assert r.attack == 1.0 and r.defense == 1.0 and r.matches == 0


def test_over_under_complementary():
    m = PoissonGoalsModel().fit(MATCHES)
    fc = m.forecast("a", "b")
    assert abs(fc.prob_over(2.5) + fc.prob_under(2.5) - 1.0) < 1e-9


def test_result_probabilities_sum_to_one():
    m = PoissonGoalsModel().fit(MATCHES)
    res = m.forecast("a", "c").prob_result()
    # la grilla se trunca en MAX_GOALS=10 goles/lado: con lambda alto se pierde una
    # fracción ínfima de masa en la cola (en lambdas reales de fútbol es ~1e-7).
    assert abs(res["home"] + res["draw"] + res["away"] - 1.0) < 2e-3
    assert res["home"] > res["away"]  # A (fuerte) local vs C (debil)


def test_btts_formula():
    m = PoissonGoalsModel().fit(MATCHES)
    fc = m.forecast("a", "b")
    expected = (1 - math.exp(-fc.lambda_home)) * (1 - math.exp(-fc.lambda_away))
    assert abs(fc.prob_btts() - expected) < 1e-12


def test_neutral_venue_is_symmetric_split():
    """En sede neutral, invertir local/visita intercambia exactamente los lambdas."""
    m = PoissonGoalsModel(neutral=True).fit(MATCHES)
    ab = m.forecast("a", "b")
    ba = m.forecast("b", "a")
    assert abs(ab.lambda_home - ba.lambda_away) < 1e-9
    assert abs(ab.lambda_away - ba.lambda_home) < 1e-9


def test_non_neutral_applies_home_advantage():
    m = PoissonGoalsModel(neutral=False).fit(MATCHES)
    m.home_factor = 2.0  # forzar ventaja local marcada
    same = m.forecast("a", "a")
    assert same.lambda_home > same.lambda_away  # mismo equipo: gana el local


def test_top_scores_sorted_and_probable():
    m = PoissonGoalsModel().fit(MATCHES)
    tops = m.forecast("a", "c").top_scores(3)
    assert len(tops) == 3
    assert tops[0][2] >= tops[1][2] >= tops[2][2]


def test_confidence_scales_with_data():
    m = PoissonGoalsModel().fit(MATCHES)
    fc = m.forecast("a", "b")
    assert fc.confidence(high_at=3, low_below=1) == "HIGH"     # >=3 partidos cada uno
    assert fc.confidence(high_at=99, low_below=1) == "MEDIUM"
