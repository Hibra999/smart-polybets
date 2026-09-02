#!/usr/bin/env python
"""Captura y evalúa precios NFL de Polymarket a T-24h, sin operar.

Todo acceso al venue pasa por ``venue.discovery`` y ``venue.books``. El valor de
``price_history`` se conserva como precio histórico sin asumir que sea trade, midpoint
o ask; la API oficial no especifica esa semántica.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adapters.american_football.nfl_pipeline import NFLPipeline, in_active_history
from agent.workflows.pipeline_backtest import AWAY, DRAW, HOME, simulate_games
from research.functions.calibration import (
    expected_calibration_error,
    multiclass_brier,
    multiclass_log_loss,
)
from risk.functions.kelly import fractional_kelly
from scripts.migrate_nfl_data import TEAM_NAMES
from tournaments.registry import load_active_strategy
from venue.books import price_history
from venue.discovery import list_events
from venue.matching import canon

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "nfl_2026" / "nfl_2026.sqlite"
DEFAULT_CSV = ROOT / "data" / "nfl_2026" / "ingest" / "polymarket_t24h.csv"
DEFAULT_REPORT = (
    ROOT
    / "editorial"
    / "reports"
    / "nfl_2026"
    / f"{datetime.now(UTC):%Y-%m-%d}_pm-history.json"
)
TAG_ID = 450
CSV_FIELDS = (
    "fixture_id",
    "season",
    "kickoff_utc",
    "home_team_id",
    "away_team_id",
    "condition_id",
    "home_token_id",
    "away_token_id",
    "snapshot_utc",
    "home_price_t24h",
    "fees_enabled",
)


def _team_codes() -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for code, name in TEAM_NAMES.items():
        result[canon(name)].add(code)
    return result


def _fixture_rows(db: Path) -> list[dict]:
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    rows = [
        dict(row)
        for row in connection.execute(
            "SELECT id,week_id,home_team_id,away_team_id,kickoff_utc,home_score,"
            "away_score FROM fixture WHERE status='finished' "
            "AND week_id LIKE '%_REG_w%' AND substr(week_id,1,4) IN ('2024','2025')"
        )
    ]
    connection.close()
    return rows


def match_contracts(events: list, fixtures: list[dict]) -> list[dict]:
    """Cruza moneylines completos por equipos y kickoff; excluye derivados e in-play."""
    codes = _team_codes()
    matched: dict[str, dict] = {}
    for event in events:
        for market in getattr(event, "markets", None) or []:
            sports = getattr(market, "sports", None)
            if getattr(sports, "sports_market_type", None) != "moneyline":
                continue
            slug = str(getattr(market, "slug", "") or "")
            if not re.search(r"\d{4}-\d{2}-\d{2}$", slug):
                continue
            outcomes = getattr(market, "outcomes", None)
            first = getattr(outcomes, "yes", None)
            second = getattr(outcomes, "no", None)
            first_codes = codes.get(canon(getattr(first, "label", "")), set())
            second_codes = codes.get(canon(getattr(second, "label", "")), set())
            kickoff = getattr(sports, "game_start_time", None)
            if not first_codes or not second_codes or kickoff is None:
                continue
            candidates = []
            for fixture in fixtures:
                teams = {fixture["home_team_id"], fixture["away_team_id"]}
                if not teams & first_codes or not teams & second_codes:
                    continue
                fixture_time = datetime.fromisoformat(fixture["kickoff_utc"])
                difference = abs((fixture_time - kickoff).total_seconds())
                if difference <= 4 * 3600:
                    candidates.append((difference, fixture))
            if not candidates:
                continue
            fixture = min(candidates, key=lambda item: item[0])[1]
            first_is_home = fixture["home_team_id"] in first_codes
            matched[fixture["id"]] = {
                "fixture_id": fixture["id"],
                "season": fixture["week_id"][:4],
                "kickoff_utc": fixture["kickoff_utc"],
                "home_team_id": fixture["home_team_id"],
                "away_team_id": fixture["away_team_id"],
                "condition_id": str(market.condition_id),
                "home_token_id": str(first.token_id if first_is_home else second.token_id),
                "away_token_id": str(second.token_id if first_is_home else first.token_id),
                "snapshot_utc": "",
                "home_price_t24h": "",
                "fees_enabled": bool(getattr(getattr(market, "trading", None), "fees_enabled", False)),
            }
    return sorted(matched.values(), key=lambda row: row["kickoff_utc"])


def snapshot_t24h(token_id: str, kickoff_utc: str) -> tuple[int, float] | None:
    kickoff = datetime.fromisoformat(kickoff_utc)
    target = kickoff - timedelta(hours=24)
    history = price_history(
        token_id,
        start_ts=int((target - timedelta(days=7)).timestamp()),
        end_ts=int(target.timestamp()),
        fidelity=5,
    )
    eligible = [(timestamp, price) for timestamp, price in history if timestamp <= target.timestamp()]
    if not eligible:
        return None
    timestamp, price = max(eligible, key=lambda item: item[0])
    return (timestamp, price) if 0 < price < 1 else None


def refresh(db: Path) -> tuple[list[dict], dict]:
    events = list_events(TAG_ID, closed=True, limit=3000)
    starts = [
        getattr(getattr(event, "schedule", None), "start_time", None)
        for event in events
    ]
    starts = [value for value in starts if value is not None]
    rows = match_contracts(events, _fixture_rows(db))
    failures = 0
    for index, row in enumerate(rows, start=1):
        try:
            snapshot = snapshot_t24h(row["home_token_id"], row["kickoff_utc"])
        except Exception as exc:  # noqa: BLE001 - una serie ausente no invalida el dataset
            failures += 1
            print(f"[WARN] {row['fixture_id']}: {type(exc).__name__}: {exc}")
            continue
        if snapshot is not None:
            row["snapshot_utc"] = datetime.fromtimestamp(snapshot[0], UTC).isoformat()
            row["home_price_t24h"] = snapshot[1]
        if index % 25 == 0 or index == len(rows):
            valid = sum(row["home_price_t24h"] != "" for row in rows[:index])
            print(f"history {index}/{len(rows)}: {valid} snapshots T-24h")
    return rows, {
        "events_scanned": len(events),
        "catalog_start_utc": min(starts).isoformat() if starts else None,
        "catalog_end_utc": max(starts).isoformat() if starts else None,
        "request_failures": failures,
    }


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _all_games(db: Path) -> list[dict]:
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    rows = [
        dict(row)
        for row in connection.execute(
            "SELECT id,week_id,home_team_id,away_team_id,kickoff_utc,home_score,away_score "
            "FROM fixture WHERE status='finished' AND home_score IS NOT NULL "
            "AND week_id LIKE '%_REG_w%' ORDER BY kickoff_utc"
        )
    ]
    connection.close()
    return [row for row in rows if in_active_history(row["kickoff_utc"])]


def _metrics(probabilities: list[float], outcomes: list[int]) -> dict[str, float]:
    rows = [[1 - probability, probability] for probability in probabilities]
    return {
        "log_loss": multiclass_log_loss(rows, outcomes),
        "brier": multiclass_brier(rows, outcomes),
        "ece": expected_calibration_error(rows, outcomes),
    }


def _bootstrap_delta(
    market: list[float], challenger: list[float], outcomes: list[int]
) -> tuple[float, list[float]]:
    import numpy as np

    y = np.asarray(outcomes)
    market_p = np.clip(np.asarray(market), 1e-9, 1 - 1e-9)
    challenger_p = np.clip(np.asarray(challenger), 1e-9, 1 - 1e-9)
    market_loss = -(y * np.log(market_p) + (1 - y) * np.log(1 - market_p))
    challenger_loss = -(y * np.log(challenger_p) + (1 - y) * np.log(1 - challenger_p))
    delta = market_loss - challenger_loss
    rng = np.random.default_rng(7)
    boot = np.asarray(
        [delta[rng.integers(0, len(delta), len(delta))].mean() for _ in range(2_000)]
    )
    return float(delta.mean()), [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]


def _platt_result(normalized: list[dict]) -> dict:
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    observed = [game for game in normalized if game["target"]]
    train = [game for game in observed if game["season"] == "2024"]
    test = [game for game in observed if game["season"] == "2025"]
    x_train = np.asarray([[_logit(game["market_home"])] for game in train])
    y_train = np.asarray([int(game["winner"] == HOME) for game in train])
    x_test = np.asarray([[_logit(game["market_home"])] for game in test])
    y_test = [int(game["winner"] == HOME) for game in test]
    model = LogisticRegression(C=1_000, max_iter=2_000).fit(x_train, y_train)
    calibrated = model.predict_proba(x_test)[:, 1].tolist()

    strategy = load_active_strategy("nfl_2026", require_approved=False)
    assert strategy is not None
    bank = peak = 1000.0
    staked = 0.0
    bets = wins = 0
    max_drawdown = 0.0
    for game, model_home in zip(test, calibrated, strict=True):
        market_home = float(game["market_home"])
        side = HOME if model_home >= market_home else AWAY
        model_probability = model_home if side == HOME else 1 - model_home
        market_probability = market_home if side == HOME else 1 - market_home
        if model_probability - market_probability < float(strategy.edge_threshold_auto):
            continue
        kelly = fractional_kelly(
            model_probability,
            market_probability,
            strategy.kelly_fraction,
            bank,
            max_bet_usdc=strategy.max_bet_usdc,
            max_kelly_fraction=strategy.max_kelly_fraction,
        )
        if kelly.recommended_size_usdc < strategy.min_bet_usdc:
            continue
        stake = float(kelly.recommended_size_usdc)
        won = game["winner"] == side
        pnl = stake * (1 - market_probability) / market_probability if won else -stake
        bank += pnl
        peak = max(peak, bank)
        max_drawdown = max(max_drawdown, (peak - bank) / peak)
        staked += stake
        bets += 1
        wins += int(won)
    return {
        "split": {"fit": "2024", "test": "2025"},
        "market_2025": _metrics(
            [float(game["market_home"]) for game in test], y_test
        ),
        "platt_2025": _metrics(calibrated, y_test),
        "replay_2025": {
            "bankroll_initial": 1000.0,
            "bankroll_final": round(bank, 2),
            "roi": (bank - 1000) / 1000,
            "yield_on_staked": (bank - 1000) / staked if staked else 0.0,
            "bets": bets,
            "wins": wins,
            "losses": bets - wins,
            "win_rate": wins / bets if bets else 0.0,
            "max_drawdown": max_drawdown,
        },
        "gate": "FAIL",
    }

def _logit(probability: float) -> float:
    value = min(max(float(probability), 1e-9), 1 - 1e-9)
    return math.log(value / (1 - value))


def evaluate(db: Path, rows: list[dict], catalog: dict) -> dict:
    valid = {
        row["fixture_id"]: row
        for row in rows
        if row.get("home_price_t24h") not in (None, "")
    }
    games = _all_games(db)
    pipe = NFLPipeline()
    probabilities = {"market": [], "trueskill": []}
    outcomes: list[int] = []
    normalized = []
    for game in games:
        observation = valid.get(game["id"])
        snap = pipe.prematch(game["home_team_id"], game["away_team_id"])
        tied = game["home_score"] == game["away_score"]
        if observation and not tied:
            probabilities["market"].append(float(observation["home_price_t24h"]))
            probabilities["trueskill"].append(float(snap["p_home"]))
            outcomes.append(int(game["home_score"] > game["away_score"]))
        winner = (
            HOME
            if game["home_score"] > game["away_score"]
            else AWAY if game["away_score"] > game["home_score"] else DRAW
        )
        price = float(observation["home_price_t24h"]) if observation else None
        normalized.append(
            {
                "id": game["id"],
                "home": game["home_team_id"],
                "away": game["away_team_id"],
                "home_score": int(game["home_score"]),
                "away_score": int(game["away_score"]),
                "winner": winner,
                "kickoff_utc": game["kickoff_utc"],
                "phase": "regular_season",
                "market_home": price,
                "market_away": 1 - price if price is not None else None,
                "target": observation is not None and not tied,
                "season": game["week_id"][:4],
            }
        )
        pipe.process_match(
            game["home_team_id"],
            game["away_team_id"],
            int(game["home_score"]),
            int(game["away_score"]),
        )

    strategy = load_active_strategy("nfl_2026", require_approved=False)
    assert strategy is not None
    source = "Polymarket CLOB price_history T-24h (price semantics unspecified)"
    replay = simulate_games(
        "nfl_2026", normalized, NFLPipeline(), strategy, bankroll=1000, price_source=source
    )
    seasons = {}
    for season in sorted({game["season"] for game in normalized if game["target"]}):
        season_games = [
            {**game, "target": game["target"] and game["season"] == season}
            for game in normalized
            if game["season"] <= season
        ]
        seasons[season] = simulate_games(
            "nfl_2026",
            season_games,
            NFLPipeline(),
            strategy,
            bankroll=1000,
            price_source=source,
        )["performance"]

    no_ties = len(outcomes)
    delta, bootstrap = _bootstrap_delta(
        probabilities["market"], probabilities["trueskill"], outcomes
    )
    stable = bool(seasons) and all(item["roi"] > 0 for item in seasons.values())
    all_fee_disabled = all(not _truthy(row["fees_enabled"]) for row in valid.values())
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": {
            "catalog": "Polymarket public NFL tag 450",
            "price": "CLOB price_history at or before T-24h",
            "price_semantics": "official API documents only historical price data",
            **catalog,
        },
        "coverage": {
            "contracts_matched": len(rows),
            "snapshots_valid": len(valid),
            "observations_no_tie": no_ties,
        },
        "market_only": _metrics(probabilities["market"], outcomes),
        "trueskill_active": _metrics(probabilities["trueskill"], outcomes),
        "delta_log_loss_market_minus_trueskill": delta,
        "bootstrap_95_ci": bootstrap,
        "continuous_replay": replay["performance"],
        "season_replays": seasons,
        "platt_calibration": _platt_result(normalized),
        "costs": {
            "contracts_indicated_fees_disabled": all_fee_disabled,
            "historical_order_books_available": False,
            "slippage_reconstructed": False,
        },
        "hypotheses_tested": ["active_trueskill", "market_logit_platt"],
        "promotion_gate": "FAIL",
        "gate_reasons": [
            "no se reconstruyó slippage histórico",
            *([] if stable else ["ROI no es positivo y estable por temporada"]),
            *([] if no_ties >= 300 else ["menos de 300 decisiones liquidadas fuera de muestra"]),
        ],
        "strategy_changed": False,
    }


def _truthy(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    if args.refresh or not args.csv.exists():
        rows, catalog = refresh(args.db)
        write_csv(args.csv, rows)
    else:
        rows = read_csv(args.csv)
        source = {}
        if args.output.exists():
            source = json.loads(args.output.read_text(encoding="utf-8")).get("source", {})
        catalog = {
            key: source.get(key)
            for key in (
                "events_scanned",
                "catalog_start_utc",
                "catalog_end_utc",
                "request_failures",
            )
        }
    report = evaluate(args.db, rows, catalog)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    print(f"CSV: {args.csv}")
    print(f"Reporte: {args.output}")


if __name__ == "__main__":
    main()
