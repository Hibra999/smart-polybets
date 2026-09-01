"""Evalúa un challenger NFL EPA+mercado sin modificar la estrategia activa.

Split fijo y auditable: train 2022-23, calibración 2024, holdout 2025. Los features
son pre-partido y se actualizan después del resultado (walk-forward).
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.american_football.nfl_ensemble import NFLEnsemblePipeline
from agent.workflows.nfl_backtest import american_to_decimal
from research.functions.calibration import (
    expected_calibration_error,
    multiclass_brier,
    multiclass_log_loss,
    power_devig,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "data" / "nfl_2026" / "nfl_2026.sqlite"
FEATURES = (
    "market_logit", "elo_logit", "bayes_logit", "trueskill_logit",
    "epa_net_diff", "success_diff", "explosive_diff", "proe_diff",
)


def _logit(probability: float) -> float:
    p = min(max(probability, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _rolling(history: dict[str, list[dict]], team: str, key: str) -> float:
    values = [row[key] for row in history.get(team, [])[-8:] if row.get(key) is not None]
    if not values:
        return 0.0
    weights = [0.85 ** age for age in range(len(values) - 1, -1, -1)]
    return sum(value * weight for value, weight in zip(values, weights, strict=True)) / sum(weights)


def build_rows(games: list[dict], stats: dict[str, dict[str, dict]]) -> list[dict]:
    """Construye filas pregame; reinicia ratings e historial al cambiar temporada."""
    rows: list[dict] = []
    pipe = NFLEnsemblePipeline()
    history: dict[str, list[dict]] = {}
    current_season = None
    for game in games:
        season = int(str(game["week_id"])[:4])
        if season != current_season:
            pipe, history, current_season = NFLEnsemblePipeline(), {}, season
        home, away = game["home_team_id"], game["away_team_id"]
        snap = pipe.prematch(home, away)
        enough_history = min(len(history.get(home, [])), len(history.get(away, []))) >= 4
        no_tie = game["home_score"] != game["away_score"]
        if enough_history and no_tie and game.get("moneyline_home") is not None \
                and game.get("moneyline_away") is not None:
            implied = [
                1 / american_to_decimal(game["moneyline_home"]),
                1 / american_to_decimal(game["moneyline_away"]),
            ]
            market_home = power_devig(implied)[0]
            home_net = _rolling(history, home, "offensive_epa_per_play") + _rolling(
                history, home, "defensive_epa_per_play")
            away_net = _rolling(history, away, "offensive_epa_per_play") + _rolling(
                history, away, "defensive_epa_per_play")
            rows.append({
                "fixture_id": game["id"],
                "season": season,
                "outcome": int(game["home_score"] > game["away_score"]),
                "market_home": market_home,
                "features": [
                    _logit(market_home), _logit(snap["elo"]), _logit(snap["bayes"]),
                    _logit(snap["trueskill"]), home_net - away_net,
                    _rolling(history, home, "success_rate")
                    - _rolling(history, away, "success_rate"),
                    _rolling(history, home, "explosive_play_rate")
                    - _rolling(history, away, "explosive_play_rate"),
                    _rolling(history, home, "proe") - _rolling(history, away, "proe"),
                ],
            })
        pipe.process_match(home, away, int(game["home_score"]), int(game["away_score"]))
        for team, row in stats.get(game["id"], {}).items():
            history.setdefault(team, []).append(row)
    return rows


def load_rows(db: Path) -> list[dict]:
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    games = [dict(row) for row in connection.execute(
        "SELECT id,week_id,home_team_id,away_team_id,home_score,away_score,"
        "moneyline_home,moneyline_away,kickoff_utc FROM fixture "
        "WHERE status='finished' AND week_id LIKE '%_REG_w%' ORDER BY kickoff_utc")]
    stats: dict[str, dict[str, dict]] = {}
    for row in connection.execute(
        "SELECT fixture_id,team_id,offensive_epa_per_play,defensive_epa_per_play,"
        "success_rate,explosive_play_rate,proe FROM match_team_stat"):
        values = dict(row)
        stats.setdefault(values.pop("fixture_id"), {})[values.pop("team_id")] = values
    connection.close()
    return build_rows(games, stats)


def _probability_rows(values) -> list[list[float]]:
    return [[1 - float(value), float(value)] for value in values]


def _metrics(probabilities, outcomes) -> dict[str, float]:
    rows = _probability_rows(probabilities)
    return {
        "log_loss": multiclass_log_loss(rows, outcomes),
        "brier": multiclass_brier(rows, outcomes),
        "ece": expected_calibration_error(rows, outcomes),
    }


def evaluate(rows: list[dict], *, bootstrap_samples: int = 2_000) -> dict:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    train = [row for row in rows if row["season"] in (2022, 2023)]
    calibrate = [row for row in rows if row["season"] == 2024]
    test = [row for row in rows if row["season"] == 2025]
    if min(map(len, (train, calibrate, test)), default=0) < 50:
        raise ValueError("se requieren >=50 juegos en train, calibración y holdout")

    def arrays(part):
        return np.asarray([row["features"] for row in part]), np.asarray(
            [row["outcome"] for row in part])

    x_train, y_train = arrays(train)
    x_cal, y_cal = arrays(calibrate)
    x_test, y_test = arrays(test)

    def fitted_probabilities(feature_indices: list[int]):
        base = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2_000, C=0.5))
        base.fit(x_train[:, feature_indices], y_train)
        platt = LogisticRegression(C=1_000, max_iter=2_000)
        platt.fit(base.decision_function(x_cal[:, feature_indices]).reshape(-1, 1), y_cal)
        scores = base.decision_function(x_test[:, feature_indices]).reshape(-1, 1)
        return platt.predict_proba(scores)[:, 1]

    market = fitted_probabilities([0])
    challenger = fitted_probabilities(list(range(len(FEATURES))))
    outcomes = y_test.tolist()
    market_losses = -(y_test * np.log(market) + (1 - y_test) * np.log(1 - market))
    challenger_losses = -(y_test * np.log(challenger) + (1 - y_test) * np.log(1 - challenger))
    delta = market_losses - challenger_losses
    rng = np.random.default_rng(7)
    boot = np.asarray([
        delta[rng.integers(0, len(delta), len(delta))].mean()
        for _ in range(bootstrap_samples)
    ])
    market_metrics = _metrics(market, outcomes)
    challenger_metrics = _metrics(challenger, outcomes)
    ci = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
    promote = (
        len(test) >= 200 and ci[0] > 0
        and challenger_metrics["brier"] <= market_metrics["brier"]
        and challenger_metrics["ece"] <= market_metrics["ece"] + 0.01
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "split": {"train": "2022-2023", "calibration": "2024", "holdout": "2025"},
        "sample_sizes": {"train": len(train), "calibration": len(calibrate), "holdout": len(test)},
        "features": list(FEATURES),
        "market_only": market_metrics,
        "challenger": challenger_metrics,
        "delta_log_loss_market_minus_challenger": float(delta.mean()),
        "bootstrap_95_ci": ci,
        "promotion_gate": "PASS" if promote else "FAIL",
        "strategy_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(load_rows(args.db))
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Reporte: {args.output}")


if __name__ == "__main__":
    main()
