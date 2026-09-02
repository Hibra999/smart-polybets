"""Evalúa los challengers preregistrados LMX-MKT-1X2-01 y NFL-SPREAD-ML-01."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from agent.workflows.nfl_backtest import american_to_decimal
from execution.functions.fees import taker_fee_usdc
from scripts.ligamx_backtest import load_matches, outcome_idx

REPO_ROOT = Path(__file__).resolve().parent.parent
NFL_DB = REPO_ROOT / "data" / "nfl_2026" / "nfl_2026.sqlite"
FEE_BPS = 500
SLIPPAGE_PRICE = 0.01
INITIAL_BANKROLL = 1_000.0
KELLY_FRACTION = 0.25
MIN_BET = 5.0
MAX_BET = 25.0
LIGA_TARGETS = ("2022/2023", "2023/2024", "2024/2025", "2025/2026")
NFL_TARGETS = (2022, 2023, 2024, 2025)


def _execution_price(decimal_odds: float) -> float:
    return min(0.99, 1.0 / decimal_odds + SLIPPAGE_PRICE)


def _fee(stake: float, price: float) -> float:
    shares = Decimal(str(stake)) / Decimal(str(price))
    return float(taker_fee_usdc(shares, price, FEE_BPS))


def simulate(forecasts: list[dict]) -> dict:
    """Liquida una posición máxima por evento con los costos preregistrados."""
    bank = peak = INITIAL_BANKROLL
    max_drawdown = 0.0
    bets: list[dict] = []
    seasons: dict[str, dict] = {}
    for forecast in forecasts:
        season = str(forecast["season"])
        season_row = seasons.setdefault(season, {"bets": 0, "profit": 0.0, "staked": 0.0})
        candidates = []
        for side, (probability, odds) in enumerate(
            zip(forecast["probabilities"], forecast["odds"], strict=True)
        ):
            price = _execution_price(odds)
            fee_ratio = _fee(1.0, price)
            net_ev = probability / price - 1.0 - fee_ratio
            if net_ev > 0:
                candidates.append((net_ev, side, probability, price))
        if not candidates:
            continue

        net_ev, side, probability, price = max(candidates)
        raw_stake = bank * KELLY_FRACTION * max(0.0, (probability - price) / (1.0 - price))
        stake = min(MAX_BET, raw_stake)
        fee = _fee(stake, price)
        if stake < MIN_BET or stake + fee > bank:
            continue

        won = side == forecast["winner"]
        gross_pnl = stake * (1.0 - price) / price if won else -stake
        pnl = gross_pnl - fee
        bank += pnl
        peak = max(peak, bank)
        max_drawdown = max(max_drawdown, (peak - bank) / peak)
        season_row["bets"] += 1
        season_row["profit"] += pnl
        season_row["staked"] += stake
        bets.append({
            "event_id": forecast["event_id"], "season": season, "side": side,
            "probability": probability, "execution_price": price, "net_ev": net_ev,
            "stake": stake, "fee": fee, "won": won, "pnl": pnl,
        })

    staked = sum(bet["stake"] for bet in bets)
    profit = bank - INITIAL_BANKROLL
    for row in seasons.values():
        row["profit"] = round(row["profit"], 2)
        row["staked"] = round(row["staked"], 2)
        row["yield_on_staked"] = row["profit"] / row["staked"] if row["staked"] else 0.0
    ci = _bootstrap_yield(bets)
    profitable_seasons = sum(row["profit"] > 0 for row in seasons.values())
    point_gate = profit > 0 and staked > 0 and profitable_seasons >= 3 and len(bets) >= 100
    return {
        "performance": {
            "bankroll_initial": INITIAL_BANKROLL, "bankroll_final": round(bank, 2),
            "profit": round(profit, 2), "roi": profit / INITIAL_BANKROLL,
            "yield_on_staked": profit / staked if staked else 0.0, "bets": len(bets),
            "wins": sum(bet["won"] for bet in bets), "staked": round(staked, 2),
            "fees": round(sum(bet["fee"] for bet in bets), 2),
            "max_drawdown": max_drawdown, "profitable_seasons": profitable_seasons,
            "bootstrap_yield_95_ci": ci,
        },
        "seasons": seasons,
        "point_profit_gate": "PASS" if point_gate else "FAIL",
        "robust_profit_gate": "PASS" if point_gate and ci[0] > 0 else "FAIL",
        "bets": bets,
    }


def _bootstrap_yield(bets: list[dict], samples: int = 2_000) -> list[float]:
    if not bets:
        return [0.0, 0.0]
    import numpy as np

    pnl = np.asarray([bet["pnl"] for bet in bets])
    stakes = np.asarray([bet["stake"] for bet in bets])
    rng = np.random.default_rng(7)
    yields = []
    for _ in range(samples):
        indices = rng.integers(0, len(bets), len(bets))
        yields.append(float(pnl[indices].sum() / stakes[indices].sum()))
    return [float(np.percentile(yields, 2.5)), float(np.percentile(yields, 97.5))]


def _power_probabilities(odds: tuple[float, ...], beta: float) -> tuple[float, ...]:
    weights = [(1.0 / odd) ** beta for odd in odds]
    total = sum(weights)
    return tuple(weight / total for weight in weights)


def _fit_beta(matches: list[dict]) -> float:
    from scipy.optimize import minimize_scalar

    def loss(beta: float) -> float:
        total = 0.0
        for match in matches:
            probabilities = _power_probabilities((match["oh"], match["od"], match["oa"]), beta)
            total -= math.log(max(probabilities[outcome_idx(match["hg"], match["ag"])], 1e-12))
        return total / len(matches)

    result = minimize_scalar(loss, bounds=(0.5, 2.0), method="bounded")
    if not result.success:
        raise RuntimeError(f"No se pudo ajustar beta: {result.message}")
    return float(result.x)


def liga_mx() -> dict:
    matches = load_matches()
    forecasts = []
    folds = []
    for target in LIGA_TARGETS:
        target_rows = [match for match in matches if match["season"] == target]
        if not target_rows:
            raise ValueError(f"Sin partidos Liga MX para {target}")
        cutoff = min(match["date"] for match in target_rows)
        train = [match for match in matches if match["date"] < cutoff]
        beta = _fit_beta(train)
        folds.append({"season": target, "train": len(train), "beta": beta})
        for index, match in enumerate(target_rows, start=1):
            forecasts.append({
                "event_id": f"mex-{target}-{index}", "season": target,
                "probabilities": _power_probabilities(
                    (match["oh"], match["od"], match["oa"]), beta
                ),
                "odds": (match["max_oh"], match["max_od"], match["max_oa"]),
                "winner": outcome_idx(match["hg"], match["ag"]),
            })
    return {"hypothesis": "LMX-MKT-1X2-01", "folds": folds, **simulate(forecasts)}


def _load_nfl() -> list[dict]:
    connection = sqlite3.connect(NFL_DB)
    connection.row_factory = sqlite3.Row
    rows = [dict(row) for row in connection.execute(
        "SELECT id,week_id,home_score,away_score,spread_home,moneyline_home,moneyline_away "
        "FROM fixture WHERE status='finished' AND week_id LIKE '%_REG_w%' "
        "AND spread_home IS NOT NULL AND moneyline_home IS NOT NULL "
        "AND moneyline_away IS NOT NULL ORDER BY kickoff_utc"
    )]
    connection.close()
    for row in rows:
        row["season"] = int(row["week_id"][:4])
    return [row for row in rows if row["home_score"] != row["away_score"]]


def nfl() -> dict:
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    rows = _load_nfl()
    forecasts = []
    folds = []
    for target in NFL_TARGETS:
        train = [row for row in rows if 2010 <= row["season"] < target]
        target_rows = [row for row in rows if row["season"] == target]
        model = LogisticRegression(C=1_000, max_iter=2_000)
        model.fit(
            np.asarray([[row["spread_home"]] for row in train]),
            np.asarray([int(row["home_score"] > row["away_score"]) for row in train]),
        )
        folds.append({
            "season": target, "train": len(train),
            "intercept": float(model.intercept_[0]), "spread_coef": float(model.coef_[0, 0]),
        })
        home_probabilities = model.predict_proba(
            np.asarray([[row["spread_home"]] for row in target_rows])
        )[:, 1]
        for row, home_probability in zip(target_rows, home_probabilities, strict=True):
            forecasts.append({
                "event_id": row["id"], "season": target,
                "probabilities": (float(home_probability), 1.0 - float(home_probability)),
                "odds": (
                    american_to_decimal(row["moneyline_home"]),
                    american_to_decimal(row["moneyline_away"]),
                ),
                "winner": int(row["home_score"] <= row["away_score"]),
            })
    return {"hypothesis": "NFL-SPREAD-ML-01", "folds": folds, **simulate(forecasts)}


def run() -> dict:
    results = {"liga_mx_2026": liga_mx(), "nfl_2026": nfl()}
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "parameters": {
            "fee_bps": FEE_BPS, "slippage_price": SLIPPAGE_PRICE,
            "kelly_fraction": KELLY_FRACTION, "min_bet": MIN_BET, "max_bet": MAX_BET,
        },
        "both_robust_profit": all(
            result["robust_profit_gate"] == "PASS" for result in results.values()
        ),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Reporte: {args.output}")


if __name__ == "__main__":
    main()
