"""Experimento challenger multiclase Liga MX contra el cierre de mercado.

Diseño (walk-forward, sin lookahead):
  - Features de cada partido calculados SOLO con partidos anteriores (replay
    cronológico de Elo con localía+ρ, TrueSkill y Poisson expansivo).
  - Warmup 2022/23 · train 2023/24 · calibración 2024/25 · holdout 2025/26.
  - Modelos: HistGradientBoosting y logística, calibrados por Platt multinomial,
    con referencias Poisson, Dixon-Coles y mercado de-vig.
  - Test de información incremental: Logística sobre [prob. del mercado] vs
    [mercado + nuestros features] — si no mejora, los features NO agregan nada
    por encima del precio (no hay edge de modelo contra el cierre).

    python scripts/ligamx_ml_experiment.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from adapters.football.poisson import PoissonGoalsModel, TimeDecayDixonColesModel
from adapters.football.strength_models import EloSystem
from adapters.football.trueskill import TrueSkillSystem
from scripts.ligamx_backtest import (
    SeasonTracker,
    load_matches,
    market_probs,
    outcome_idx,
)

HOME_ADV, RHO = 80.0, 0.80
SEASONS = {"2022/2023", "2023/2024", "2024/2025", "2025/2026"}
TEST_SEASON = "2025/2026"
TRAIN_SEASON = "2023/2024"
CALIBRATION_SEASON = "2024/2025"
REFIT_EVERY = 9


def build_dataset():
    """X (features walk-forward), y (H/D/A), mkt (probs devigged), season por fila."""
    matches = load_matches(SEASONS)
    elo = EloSystem(k=40.0, home_adv=HOME_ADV)
    tracker = SeasonTracker(elo, rho=RHO)
    ts = TrueSkillSystem()
    ts.seed_from_elo({})  # arranca vacío: mu=25 default por get
    seen: list[tuple[str, str, int, int]] = []
    dated_seen = []
    poisson = PoissonGoalsModel(neutral=False).fit(seen)
    dixon_coles = TimeDecayDixonColesModel(neutral=False)
    since_fit = 0

    X, y, mkt, seasons = [], [], [], []
    for m in matches:
        tracker.on_match_start(m)
        mp = market_probs(m)
        # features PRE-partido
        rh, ra = ts.ratings.get(m["home"]), ts.ratings.get(m["away"])
        mu_h = rh.mu if rh else 25.0
        mu_a = ra.mu if ra else 25.0
        sig_h = rh.sigma if rh else 8.333
        sig_a = ra.sigma if ra else 8.333
        fc = poisson.forecast(m["home"], m["away"])
        pr = fc.prob_result()
        dc = dixon_coles.forecast(m["home"], m["away"]).prob_result()
        feats = [
            elo.get(m["home"]) + HOME_ADV, elo.get(m["away"]),
            elo.get(m["home"]) + HOME_ADV - elo.get(m["away"]),
            elo.expected_home(m["home"], m["away"]),
            mu_h, mu_a, mu_h - mu_a, sig_h + sig_a,
            ts.win_probability(m["home"], m["away"]),
            fc.lambda_home, fc.lambda_away, fc.expected_total,
            abs(fc.lambda_home - fc.lambda_away),
            pr["home"], pr["draw"], pr["away"],
            dc["home"], dc["draw"], dc["away"],
        ]
        X.append(feats)
        y.append(outcome_idx(m["hg"], m["ag"]))
        mkt.append(list(mp) if mp else [np.nan] * 3)
        seasons.append(m["season"])
        # avanzar modelos
        elo.update_match(m["home"], m["away"], m["hg"], m["ag"])
        ts.update_match(m["home"], m["away"], m["hg"], m["ag"])
        tracker.on_match_end(m)
        seen.append((m["home"], m["away"], m["hg"], m["ag"]))
        dated_seen.append((m["date"], m["home"], m["away"], m["hg"], m["ag"]))
        since_fit += 1
        if since_fit >= REFIT_EVERY:
            poisson = PoissonGoalsModel(neutral=False).fit(seen)
            dixon_coles = TimeDecayDixonColesModel(neutral=False).fit(
                dated_seen, as_of=m["date"])
            since_fit = 0
    return (np.array(X), np.array(y), np.array(mkt, dtype=float), np.array(seasons))


def scores(p: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """(log-loss, brier 3-clases)."""
    eps = 1e-9
    ll = -np.mean(np.log(np.clip(p[np.arange(len(y)), y], eps, None)))
    onehot = np.zeros_like(p)
    onehot[np.arange(len(y)), y] = 1.0
    brier = float(np.mean(np.sum((p - onehot) ** 2, axis=1) / 3))
    return float(ll), brier


def main() -> None:
    print("Construyendo dataset walk-forward…")
    X, y, mkt, seasons = build_dataset()
    tr = seasons == TRAIN_SEASON
    cal = seasons == CALIBRATION_SEASON
    te = (seasons == TEST_SEASON) & ~np.isnan(mkt).any(axis=1)
    print(f"train={tr.sum()}  calibration={cal.sum()}  test={te.sum()}  features={X.shape[1]}")

    results: dict[str, tuple[float, float]] = {}

    # referencias
    poisson_p = X[te][:, 13:16]
    dixon_coles_p = X[te][:, 16:19]
    results["Poisson 1X2"] = scores(poisson_p, y[te])
    results["Dixon-Coles temporal"] = scores(dixon_coles_p, y[te])
    results["Mercado (cierre devig)"] = scores(mkt[te], y[te])

    def calibrated(model, train_x, train_y, calibration_x, calibration_y, test_x):
        model.fit(train_x, train_y)
        platt = LogisticRegression(max_iter=2000, C=1000)
        platt.fit(np.log(np.clip(model.predict_proba(calibration_x), 1e-6, 1)), calibration_y)
        return platt.predict_proba(np.log(np.clip(model.predict_proba(test_x), 1e-6, 1)))

    boost = HistGradientBoostingClassifier(
        max_iter=250, max_leaf_nodes=15, min_samples_leaf=20,
        l2_regularization=1.0, random_state=7)
    results["Gradient boosting (calibrado)"] = scores(
        calibrated(boost, X[tr], y[tr], X[cal], y[cal], X[te]), y[te])

    # logística multinomial (baseline lineal sobre los mismos features, escalados)
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    results["Logística (calibrada)"] = scores(
        calibrated(lr, X[tr], y[tr], X[cal], y[cal], X[te]), y[te])

    # ── test de información incremental sobre el MERCADO ────────────────────
    tr_odds = tr & ~np.isnan(mkt).any(axis=1)
    cal_odds = cal & ~np.isnan(mkt).any(axis=1)
    logit_mkt = np.log(np.clip(mkt, 1e-6, 1))  # log-probs del mercado
    lr_m = LogisticRegression(max_iter=2000)
    results["Logística: solo mercado"] = scores(calibrated(
        lr_m, logit_mkt[tr_odds], y[tr_odds], logit_mkt[cal_odds], y[cal_odds],
        logit_mkt[te]), y[te])
    both = np.hstack([logit_mkt, X])
    lr_b = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    results["Logística: mercado + features"] = scores(calibrated(
        lr_b, both[tr_odds], y[tr_odds], both[cal_odds], y[cal_odds], both[te]), y[te])

    print(f"\n=== Test 2025/26 (n={te.sum()}) — log-loss / Brier3 (menor = mejor) ===")
    for name, (ll, br) in results.items():
        print(f"  {name:32s} logloss={ll:.4f}  brier3={br:.5f}")

    delta = results["Logística: solo mercado"][0] - results["Logística: mercado + features"][0]
    print(f"\n  Información incremental de nuestros features sobre el cierre: "
          f"Δlogloss={delta:+.4f} ({'APORTAN algo' if delta > 0.002 else 'NO aportan nada material'})")


if __name__ == "__main__":
    main()
