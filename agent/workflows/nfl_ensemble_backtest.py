"""Backtest del ensemble NFL: prueba permutaciones (elo/bayes/trueskill/blends) y
optimiza los pesos del blend + el threshold de edge.

Cada combo se backtestea con Kelly fraccional (predict-then-update) contra el
moneyline real, opcionalmente sin vig. Migra el `sweep_strategies` de sports_bet
al framework.
"""
from __future__ import annotations

from decimal import Decimal

from adapters.american_football.db_reader import AmericanFootballDBReader
from adapters.american_football.nfl_ensemble import NFLEnsemblePipeline
from agent.workflows.nfl_backtest import american_to_decimal
from risk.functions.kelly import fractional_kelly

MODELS = ("elo", "bayes", "trueskill")


def load_games(tournament_id: str = "nfl_2026") -> list[dict]:
    r = AmericanFootballDBReader(tournament_id)
    return r.query(
        "SELECT home_team_id,away_team_id,home_score,away_score,winner_team_id,"
        "moneyline_home,moneyline_away,week_id FROM fixture "
        "WHERE status='finished' AND home_score IS NOT NULL ORDER BY kickoff_utc ASC"
    )


def _prob_home(snap: dict, weights: dict[str, float]) -> float:
    tot = sum(weights.values()) or 1.0
    return sum(weights.get(m, 0.0) * snap[m] for m in MODELS) / tot


def simulate_combo(games: list[dict], weights: dict[str, float], *, season: int = 2025,
                   bankroll0: float = 1000.0, devig: bool = False, edge_threshold: float = 0.0,
                   kelly_fraction: float = 0.25, max_bet: float = 60.0,
                   max_kelly: float = 0.25, min_bet: float = 5.0, warmup: int = 4,
                   underdogs_only: bool = False, per_season_reset: bool = True,
                   collect_bets: bool = False) -> dict:
    """`underdogs_only=True`: apuesta SOLO al underdog del mercado (la cuota más
    alta), y solo si el modelo le da más prob que el mercado (value en el dog).

    `per_season_reset=True` (default): cada temporada es independiente — los ratings
    arrancan fresh al inicio del año y se construyen DENTRO de la campaña (sin
    arrastre histórico). Con warmup, no se apuesta hasta que los equipos jugaron N."""
    pipe = NFLEnsemblePipeline()
    if per_season_reset:
        games = [g for g in games if (g["week_id"] or "").startswith(f"{season}_")]
    bankroll = Decimal(str(bankroll0))
    peak = bankroll
    max_dd = Decimal("0")
    n = wins = 0
    staked = Decimal("0")
    bets: list[dict] = []
    tag = f"{season}_REG"

    for g in games:
        home, away = g["home_team_id"], g["away_team_id"]
        target = (g["week_id"] or "").startswith(tag) and g["winner_team_id"] \
            and g["moneyline_home"] is not None and g["moneyline_away"] is not None
        if target:
            snap = pipe.prematch(home, away)
            if min(snap["home_match_no"], snap["away_match_no"]) >= warmup:
                p_home = _prob_home(snap, weights)
                dh, da = american_to_decimal(g["moneyline_home"]), american_to_decimal(g["moneyline_away"])
                if underdogs_only:
                    # underdog del mercado = la cuota decimal más alta
                    if dh >= da:
                        team, model_p, ml = home, p_home, g["moneyline_home"]
                    else:
                        team, model_p, ml = away, 1.0 - p_home, g["moneyline_away"]
                elif p_home >= 0.5:
                    team, model_p, ml = home, p_home, g["moneyline_home"]
                else:
                    team, model_p, ml = away, 1.0 - p_home, g["moneyline_away"]
                dec = american_to_decimal(ml)
                if devig:
                    ih = 1.0 / american_to_decimal(g["moneyline_home"])
                    ia = 1.0 / american_to_decimal(g["moneyline_away"])
                    fair = (1.0 / dec) / (ih + ia)
                    price, dec = fair, 1.0 / fair
                else:
                    price = 1.0 / dec
                edge = model_p - price
                if edge > edge_threshold:
                    k = fractional_kelly(model_p, price, kelly_fraction, bankroll,
                                         max_bet_usdc=max_bet, max_kelly_fraction=max_kelly)
                    stake = k.recommended_size_usdc
                    if Decimal(str(min_bet)) <= stake <= bankroll:
                        won = team == g["winner_team_id"]
                        pnl = stake * Decimal(str(dec - 1)) if won else -stake
                        bankroll += pnl
                        staked += stake
                        n += 1
                        wins += won
                        peak = max(peak, bankroll)
                        max_dd = max(max_dd, peak - bankroll)
                        if collect_bets:
                            bets.append({
                                "week": int((g["week_id"] or "_w0").split("_w")[-1]),
                                "home": home, "away": away, "pick": team,
                                "is_dog": (team == home and dh >= da) or (team == away and da > dh),
                                "model_prob": round(model_p, 4), "market_prob": round(float(price), 4),
                                "edge": round(float(edge), 4), "decimal_odds": round(float(dec), 3),
                                "stake": float(round(stake, 2)), "won": bool(won),
                                "pnl": float(round(pnl, 2)), "bankroll": float(round(bankroll, 2)),
                                "winner": g["winner_team_id"],
                            })
        pipe.process_match(home, away, int(g["home_score"]), int(g["away_score"]))

    profit = bankroll - Decimal(str(bankroll0))
    return {
        "bankroll_final": float(round(bankroll, 2)),
        "roi": float(profit / Decimal(str(bankroll0))) if bankroll0 else 0.0,
        "yield": float(profit / staked) if staked else 0.0,
        "n_bets": n, "win_rate": (wins / n) if n else 0.0,
        "max_drawdown": float(round(max_dd, 2)),
        "bankroll0": bankroll0, "season": season, "bets": bets,
    }


# Pesos de las permutaciones a barrer (suman 1).
def _weight_grid() -> list[tuple[str, dict[str, float]]]:
    combos: list[tuple[str, dict[str, float]]] = [
        ("elo", {"elo": 1}), ("bayes", {"bayes": 1}), ("trueskill", {"trueskill": 1}),
        ("elo+ts", {"elo": 0.5, "trueskill": 0.5}),
        ("elo+bayes", {"elo": 0.5, "bayes": 0.5}),
        ("ts+bayes", {"trueskill": 0.5, "bayes": 0.5}),
        ("blend equal", {"elo": 1, "trueskill": 1, "bayes": 1}),
        ("elo-heavy", {"elo": 0.5, "trueskill": 0.25, "bayes": 0.25}),
        ("ts-heavy", {"elo": 0.25, "trueskill": 0.5, "bayes": 0.25}),
    ]
    return combos


def sweep(*, season: int = 2025, devig: bool = False, edge_threshold: float = 0.0,
          bankroll0: float = 1000.0) -> list[dict]:
    games = load_games()
    rows = []
    for label, w in _weight_grid():
        m = simulate_combo(games, w, season=season, devig=devig,
                           edge_threshold=edge_threshold, bankroll0=bankroll0)
        rows.append({"combo": label, "weights": w, **m})
    rows.sort(key=lambda r: r["yield"], reverse=True)
    return rows


def optimize(*, season: int = 2025, devig: bool = False, bankroll0: float = 1000.0) -> dict:
    """Grid sobre pesos del blend × edge_threshold. Devuelve el mejor por yield."""
    games = load_games()
    steps = [0.0, 0.25, 0.5, 0.75, 1.0]
    thresholds = [0.0, 0.02, 0.05, 0.08, 0.12]
    best = None
    evaluated = 0
    for we in steps:
        for wt in steps:
            wb = round(1.0 - we - wt, 2)
            if wb < 0:
                continue
            if we == wt == wb == 0:
                continue
            w = {"elo": we, "trueskill": wt, "bayes": wb}
            for thr in thresholds:
                m = simulate_combo(games, w, season=season, devig=devig,
                                   edge_threshold=thr, bankroll0=bankroll0)
                evaluated += 1
                if m["n_bets"] >= 10 and (best is None or m["yield"] > best["yield"]):
                    best = {"weights": w, "edge_threshold": thr, **m}
    return {"best": best, "evaluated": evaluated, "devig": devig}
