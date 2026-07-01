"""Backtest de la estrategia NFL (TrueSkill + Kelly) sobre una temporada.

Simula la evolución del bankroll apostando con Kelly fraccional: para cada juego
(en orden cronológico) predice con TrueSkill usando SÓLO los juegos previos
(predict-then-update, O(n)), elige el lado de mayor rating, mide el edge contra el
moneyline real (nflverse) y apuesta Kelly si el edge es positivo.

Migra la lógica de `sports_bet/test_bet_sizing.py` (kelly_criterion) al framework.
"""
from __future__ import annotations

from decimal import Decimal

from adapters.american_football.db_reader import AmericanFootballDBReader
from adapters.american_football.nfl_pipeline import NFLPipeline
from risk.functions.kelly import fractional_kelly
from tournaments.registry import load_active_strategy


def american_to_decimal(ml: float) -> float:
    return (ml / 100) + 1 if ml > 0 else (100 / abs(ml)) + 1


def simulate(tournament_id: str = "nfl_2026", *, season: int = 2025,
             bankroll0: float = 1000.0, reader: AmericanFootballDBReader | None = None,
             devig: bool = False) -> dict:
    """Backtest. Con `devig=True` apuesta contra la línea SIN vig (prob justa del
    mercado, casa sin margen): benchmark más blando para aislar el edge del modelo.
    No hay línea de apertura disponible gratis (aussportsbetting bloquea), así que
    de-vig de la línea de cierre es la mejor aproximación a una línea más batible."""
    strat = load_active_strategy(tournament_id)
    r = reader or AmericanFootballDBReader(tournament_id)

    games = r.query(
        "SELECT id,home_team_id,away_team_id,home_score,away_score,winner_team_id,"
        "moneyline_home,moneyline_away,week_id,kickoff_utc FROM fixture "
        "WHERE status='finished' AND home_score IS NOT NULL ORDER BY kickoff_utc ASC"
    )

    pipe = NFLPipeline()
    bankroll = Decimal(str(bankroll0))
    peak = bankroll
    max_dd = Decimal("0")
    bets: list[dict] = []
    curve = [float(bankroll)]
    wins = 0
    total_staked = Decimal("0")
    target_tag = f"{season}_REG"

    for g in games:
        home, away = g["home_team_id"], g["away_team_id"]
        is_target = (g["week_id"] or "").startswith(target_tag) and g["winner_team_id"]

        if is_target and g["moneyline_home"] is not None and g["moneyline_away"] is not None:
            snap = pipe.prematch(home, away)
            appr = min(snap["home_match_no"], snap["away_match_no"])
            if appr >= strat.warmup_match_no:
                # lado de mayor TrueSkill
                if snap["ts_home"] >= snap["ts_away"]:
                    side, team, model_p, ml = "HOME", home, snap["ts_home"], g["moneyline_home"]
                else:
                    side, team, model_p, ml = "AWAY", away, snap["ts_away"], g["moneyline_away"]
                dec = american_to_decimal(ml)
                if devig:
                    # quitar el vig: normalizar las dos probs implícitas a sumar 1.
                    ih, ia = 1.0 / american_to_decimal(g["moneyline_home"]), 1.0 / american_to_decimal(g["moneyline_away"])
                    fair = (1.0 / dec) / (ih + ia)
                    price = Decimal(str(fair))
                    dec = 1.0 / fair                       # paga a la cuota justa (sin margen)
                else:
                    price = Decimal(str(1.0 / dec))        # prob implícita del mercado (con vig)
                edge = Decimal(str(model_p)) - price
                if edge > 0:
                    k = fractional_kelly(model_p, price, strat.kelly_fraction, bankroll,
                                         max_bet_usdc=strat.max_bet_usdc,
                                         max_kelly_fraction=strat.max_kelly_fraction)
                    stake = k.recommended_size_usdc
                    if stake >= strat.min_bet_usdc and stake <= bankroll:
                        won = (team == g["winner_team_id"])
                        pnl = stake * Decimal(str(dec - 1)) if won else -stake
                        bankroll += pnl
                        total_staked += stake
                        wins += 1 if won else 0
                        peak = max(peak, bankroll)
                        max_dd = max(max_dd, peak - bankroll)
                        bets.append({
                            "week": g["week_id"], "home": home, "away": away,
                            "pick": team, "side": side, "model_prob": float(model_p),
                            "market_prob": float(price), "edge": float(edge),
                            "decimal_odds": round(dec, 3), "stake": float(round(stake, 2)),
                            "won": won, "pnl": float(round(pnl, 2)),
                            "bankroll": float(round(bankroll, 2)),
                            "winner": g["winner_team_id"],
                        })
                        curve.append(float(bankroll))

        pipe.process_match(home, away, int(g["home_score"]), int(g["away_score"]))

    n = len(bets)
    profit = bankroll - Decimal(str(bankroll0))
    return {
        "season": season, "strategy": strat.strategy_id, "bankroll0": bankroll0,
        "bankroll_final": float(round(bankroll, 2)),
        "profit": float(round(profit, 2)),
        "roi": float(profit / Decimal(str(bankroll0))) if bankroll0 else 0.0,
        "n_bets": n, "wins": wins,
        "win_rate": (wins / n) if n else 0.0,
        "total_staked": float(round(total_staked, 2)),
        "yield": float(profit / total_staked) if total_staked else 0.0,
        "max_drawdown": float(round(max_dd, 2)),
        "curve": curve, "bets": bets,
    }
