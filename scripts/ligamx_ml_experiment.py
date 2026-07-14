#!/usr/bin/env python
"""Experimento ML multiclase (H/D/A) para Liga MX — ¿un Random Forest sobre
nuestros features (Elo, TrueSkill, Poisson) mejora al Poisson? ¿Le agrega algo
al cierre?

Diseño (walk-forward, sin lookahead):
  - Features de cada partido calculados SOLO con partidos anteriores (replay
    cronológico de Elo con localía+ρ, TrueSkill y Poisson expansivo).
  - Train: 2022/23-2024/25 · Test: 2025/26 (mismo objetivo que el backtest).
  - Modelos: RandomForest calibrado (isotónica), Logística multinomial,
    y las referencias Poisson 1X2 y mercado (cierre promedio devigged).
  - Test de información incremental: Logística sobre [prob. del mercado] vs
    [mercado + nuestros features] — si no mejora, los features NO agregan nada
    por encima del precio (no hay edge de modelo contra el cierre).

    python scripts/ligamx_ml_experiment.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()

from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from adapters.football.wc_models import EloSystem
from adapters.football.wc_poisson import PoissonGoalsModel
from adapters.football.wc_trueskill import TrueSkillSystem
from scripts.ligamx_backtest import (
    SeasonTracker,
    load_matches,
    market_probs,
    outcome_idx,
)

HOME_ADV, RHO = 80.0, 0.80
SEASONS = {"2022/2023", "2023/2024", "2024/2025", "2025/2026"}
TEST_SEASON = "2025/2026"
REFIT_EVERY = 9


def build_dataset():
    """X (features walk-forward), y (H/D/A), mkt (probs devigged), season por fila."""
    matches = load_matches(SEASONS)
    elo = EloSystem(k=40.0, home_adv=HOME_ADV)
    tracker = SeasonTracker(elo, rho=RHO)
    ts = TrueSkillSystem()
    ts.seed_from_elo({})  # arranca vacío: mu=25 default por get
    seen: list[tuple[str, str, int, int]] = []
    poisson = PoissonGoalsModel(neutral=False).fit(seen)
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
        feats = [
            elo.get(m["home"]) + HOME_ADV, elo.get(m["away"]),
            elo.get(m["home"]) + HOME_ADV - elo.get(m["away"]),
            elo.expected_home(m["home"], m["away"]),
            mu_h, mu_a, mu_h - mu_a, sig_h + sig_a,
            ts.win_probability(m["home"], m["away"]),
            fc.lambda_home, fc.lambda_away, fc.expected_total,
            abs(fc.lambda_home - fc.lambda_away),
            pr["home"], pr["draw"], pr["away"],
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
        since_fit += 1
        if since_fit >= REFIT_EVERY:
            poisson = PoissonGoalsModel(neutral=False).fit(seen)
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
    tr = seasons != TEST_SEASON
    te = (seasons == TEST_SEASON) & ~np.isnan(mkt).any(axis=1)
    # burn-in: descartar la primera temporada del train (features fríos)
    tr = tr & (seasons != "2022/2023")
    print(f"train={tr.sum()}  test={te.sum()}  features={X.shape[1]}")

    results: dict[str, tuple[float, float]] = {}

    # referencias
    poisson_p = X[te][:, -3:]  # últimas 3 columnas = probs Poisson
    results["Poisson 1X2"] = scores(poisson_p, y[te])
    results["Mercado (cierre devig)"] = scores(mkt[te], y[te])

    # RF calibrado
    rf = CalibratedClassifierCV(
        RandomForestClassifier(n_estimators=500, min_samples_leaf=20,
                               max_features="sqrt", random_state=7, n_jobs=-1),
        method="isotonic", cv=5)
    rf.fit(X[tr], y[tr])
    results["Random Forest (calibrado)"] = scores(rf.predict_proba(X[te]), y[te])

    # logística multinomial (baseline lineal sobre los mismos features, escalados)
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))
    lr.fit(X[tr], y[tr])
    results["Logística multinomial"] = scores(lr.predict_proba(X[te]), y[te])

    # ── test de información incremental sobre el MERCADO ────────────────────
    tr_odds = tr & ~np.isnan(mkt).any(axis=1)
    logit_mkt = np.log(np.clip(mkt, 1e-6, 1))  # log-probs del mercado
    lr_m = LogisticRegression(max_iter=2000)
    lr_m.fit(logit_mkt[tr_odds], y[tr_odds])
    results["Logística: solo mercado"] = scores(lr_m.predict_proba(logit_mkt[te]), y[te])
    both = np.hstack([logit_mkt, X])
    lr_b = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    lr_b.fit(both[tr_odds], y[tr_odds])
    results["Logística: mercado + features"] = scores(lr_b.predict_proba(both[te]), y[te])

    print(f"\n=== Test 2025/26 (n={te.sum()}) — log-loss / Brier3 (menor = mejor) ===")
    for name, (ll, br) in results.items():
        print(f"  {name:32s} logloss={ll:.4f}  brier3={br:.5f}")

    delta = results["Logística: solo mercado"][0] - results["Logística: mercado + features"][0]
    print(f"\n  Información incremental de nuestros features sobre el cierre: "
          f"Δlogloss={delta:+.4f} ({'APORTAN algo' if delta > 0.002 else 'NO aportan nada material'})")


if __name__ == "__main__":
    main()
