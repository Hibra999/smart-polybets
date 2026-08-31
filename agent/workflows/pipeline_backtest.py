"""Backtest walk-forward del mismo Research → Risk → Optimization de producción."""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from adapters.american_football.db_reader import AmericanFootballDBReader
from adapters.american_football.nfl_pipeline import NFLPipeline
from adapters.football.db_reader import FootballDBReader
from adapters.football.wc_pipeline import WorldCupPipeline
from agent.workflows.nfl_backtest import american_to_decimal
from core.strategy import StrategyConfig
from core.types import ModelConfidence
from optimization.functions import size_single
from portfolio.schemas.portfolio_state import PortfolioState
from research.functions.market_scanner import PolymarketMarket
from research.functions.wc_strategy import build_worldcup_opportunity
from research.schemas.match_prediction import MatchPrediction
from risk.functions import evaluate
from scripts.ligamx_backtest import load_matches, torneo_corto
from tournaments.registry import get_config, load_active_strategy

HOME = "HOME_WIN"
AWAY = "AWAY_WIN"
DRAW = "DRAW"
_LIGA_SEASONS = {"2022/2023", "2023/2024", "2024/2025", "2025/2026"}


def _decimal(value: float) -> Decimal:
    return Decimal(str(round(float(value), 8)))


def _as_utc(value: str | datetime) -> datetime:
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _confidence(sport: str, played: int) -> ModelConfidence:
    high, medium = (8, 3) if sport == "american_football" else (5, 2)
    if played >= high:
        return ModelConfidence.HIGH
    if played >= medium:
        return ModelConfidence.MEDIUM
    return ModelConfidence.LOW


def _prediction(game: dict[str, Any], snap: dict[str, Any], strategy: StrategyConfig):
    elo = {HOME: _decimal(snap.get("p_home", 0.5)), AWAY: _decimal(snap.get("p_away", 0.5))}
    if strategy.sport == "american_football":
        ts = {HOME: _decimal(snap["ts_home"]), AWAY: _decimal(snap["ts_away"])}
        components = {"trueskill": ts}
        probabilities = ts
    else:
        bayes = {
            HOME: _decimal(snap.get("bayes_home", snap["p_home"])),
            AWAY: _decimal(snap.get("bayes_away", snap["p_away"])),
        }
        ts = {
            HOME: _decimal(snap.get("ts_home", snap["p_home"])),
            AWAY: _decimal(snap.get("ts_away", snap["p_away"])),
        }
        components = {"elo": elo, "bayes": bayes, "trueskill": ts}
        probabilities = elo

    played = min(snap["home_match_no"] - 1, snap["away_match_no"] - 1)
    kickoff = _as_utc(game["kickoff_utc"])
    return MatchPrediction(
        event_id=game["id"],
        tournament_id=strategy.tournament_id,
        sport=strategy.sport,
        market_type=strategy.market_type,
        participant_home=game["home"],
        participant_away=game["away"],
        event_start_utc=kickoff,
        event_phase=game.get("phase", "regular_season"),
        probabilities=probabilities,
        components=components,
        appearances={HOME: snap["home_match_no"], AWAY: snap["away_match_no"]},
        model_version=f"{strategy.strategy_id}-historical",
        model_confidence=_confidence(strategy.sport, played),
        sample_size=played,
        generated_at=kickoff - timedelta(hours=24),
    )


def _markets(game: dict[str, Any], strategy: StrategyConfig) -> list[PolymarketMarket]:
    volume = strategy.min_market_volume_usdc
    liquidity = max(volume, Decimal(1))
    return [
        PolymarketMarket(
            condition_id=f"backtest:{game['id']}:{side}",
            token_id=f"backtest:{game['id']}:{side}",
            model_outcome=side,
            market_probability=_decimal(game[price_key]),
            volume_usdc=volume,
            liquidity_usdc=liquidity,
            best_ask=_decimal(game[price_key]),
        )
        for side, price_key in ((HOME, "market_home"), (AWAY, "market_away"))
    ]


def simulate_games(
    tournament_id: str,
    games: list[dict[str, Any]],
    pipeline: Any,
    strategy: StrategyConfig,
    *,
    bankroll: float = 1000.0,
    price_source: str,
) -> dict[str, Any]:
    """Simula juegos normalizados; los no target sólo actualizan el modelo."""
    initial = Decimal(str(bankroll))
    bank = initial
    peak = initial
    max_drawdown = Decimal(0)
    staked = Decimal(0)
    equity_points: list[tuple[datetime, Decimal]] = []
    bets: list[dict[str, Any]] = []
    decisions = {"AUTO": 0, "REVIEW": 0, "DISCARD": 0, "SKIP": 0}
    target_games = priced_games = 0

    for game in games:
        regression = game.get("rating_regression")
        if regression is not None:
            seed = {
                team: 1500.0 + float(regression) * (rating - 1500.0)
                for team, rating in pipeline.elo.ratings.items()
            }
            pipeline.seed(seed)
        elif game.get("reset_appearances"):
            pipeline.appearances.clear()
        if game.get("target"):
            target_games += 1
            if game.get("market_home") is None or game.get("market_away") is None:
                decisions["SKIP"] += 1
            else:
                priced_games += 1
                snap = pipeline.prematch(game["home"], game["away"])
                prediction = _prediction(game, snap, strategy)
                opportunity = build_worldcup_opportunity(
                    prediction,
                    _markets(game, strategy),
                    strategy,
                    now=prediction.generated_at,
                )
                if opportunity is None:
                    decisions["SKIP"] += 1
                else:
                    cutoff = prediction.generated_at - timedelta(days=7)
                    recent = [value for ts, value in equity_points if ts >= cutoff]
                    peak_7d = max([bank, *recent])
                    current_drawdown = (peak_7d - bank) / peak_7d if peak_7d else Decimal(0)
                    state = PortfolioState(
                        bankroll_usdc=bank,
                        drawdown_7d=current_drawdown,
                        open_positions=[],
                        exposure_by_participant={},
                        as_of=prediction.generated_at,
                    )
                    verdict = evaluate(
                        opportunity, strategy, state, now=prediction.generated_at
                    )
                    mode = verdict.verdict.value
                    decisions[mode] += 1
                    if mode == "AUTO":
                        sizing = size_single(verdict, strategy)
                        if sizing.skipped or sizing.size_usdc > bank:
                            decisions["AUTO"] -= 1
                            decisions["SKIP"] += 1
                        else:
                            price = opportunity.market_probability
                            won = game["winner"] == opportunity.model_outcome
                            if opportunity.outcome == "NO":
                                won = won or game["winner"] == DRAW
                            stake = sizing.size_usdc
                            pnl = stake * (Decimal(1) - price) / price if won else -stake
                            bank += pnl
                            peak = max(peak, bank)
                            drawdown = (peak - bank) / peak if peak else Decimal(0)
                            max_drawdown = max(max_drawdown, drawdown)
                            staked += stake
                            equity_points.append((prediction.generated_at, bank))
                            bets.append(
                                {
                                    "event_id": game["id"],
                                    "pick": opportunity.model_outcome,
                                    "model_probability": float(opportunity.model_probability),
                                    "market_probability": float(price),
                                    "edge": float(opportunity.edge),
                                    "stake": float(stake),
                                    "won": won,
                                    "pnl": float(round(pnl, 2)),
                                    "bankroll": float(round(bank, 2)),
                                }
                            )

        pipeline.process_match(
            game["home"], game["away"], game["home_score"], game["away_score"]
        )

    profit = bank - initial
    wins = sum(1 for bet in bets if bet["won"])
    roi = profit / initial if initial else Decimal(0)
    yield_on_staked = profit / staked if staked else Decimal(0)
    targets = {
        "roi": strategy.roi_target,
        "win_rate": strategy.win_rate_target,
        "max_drawdown": (
            float(strategy.max_drawdown_allowed)
            if strategy.max_drawdown_allowed is not None
            else None
        ),
    }
    observed = {
        "roi": float(roi),
        "win_rate": wins / len(bets) if bets else 0.0,
        "max_drawdown": float(max_drawdown),
    }
    return {
        "tournament_id": tournament_id,
        "strategy": strategy.strategy_id,
        "strategy_version": strategy.version,
        "strategy_status": strategy.status,
        "price_source": price_source,
        "coverage": {"games": target_games, "with_price": priced_games},
        "decisions": decisions,
        "performance": {
            "bankroll_initial": float(initial),
            "bankroll_final": float(round(bank, 2)),
            "profit": float(round(profit, 2)),
            "roi": observed["roi"],
            "yield_on_staked": float(yield_on_staked),
            "bets": len(bets),
            "wins": wins,
            "losses": len(bets) - wins,
            "win_rate": observed["win_rate"],
            "staked": float(round(staked, 2)),
            "max_drawdown": observed["max_drawdown"],
        },
        "targets": {
            **targets,
            "met": {
                "roi": targets["roi"] is None or observed["roi"] >= targets["roi"],
                "win_rate": (
                    targets["win_rate"] is None
                    or observed["win_rate"] >= targets["win_rate"]
                ),
                "max_drawdown": (
                    targets["max_drawdown"] is None
                    or observed["max_drawdown"] <= targets["max_drawdown"]
                ),
            },
        },
        "assumptions": [
            "walk-forward: cada predicción usa sólo resultados anteriores",
            "precio histórico de cierre como proxy de Polymarket",
            "volumen no disponible: se asume exactamente el mínimo de la estrategia",
            "posiciones liquidadas secuencialmente; drawdown de 7 días usa el bankroll simulado",
            *(
                ["Liga MX regresa ratings 20% a la media en cada torneo corto"]
                if any(game.get("rating_regression") is not None for game in games)
                else []
            ),
        ],
        "bets": bets,
    }


def _liga_mx(season: str, bankroll: float) -> dict[str, Any]:
    strategy = load_active_strategy("liga_mx_2026", require_approved=False)
    assert strategy is not None
    cfg = get_config("liga_mx_2026")
    matches = load_matches(_LIGA_SEASONS)
    target = [match for match in matches if match["season"] == season]
    if not target:
        raise ValueError(f"Sin partidos de Liga MX para la temporada {season}")
    pipeline = WorldCupPipeline(home_adv_elo=cfg.home_adv_elo)
    for match in matches:
        if match["date"] >= target[0]["date"]:
            break
        pipeline.process_match(
            match["home"], match["away"], match["hg"], match["ag"]
        )
    pipeline.appearances.clear()

    games = []
    short_tournament = None
    for index, match in enumerate(target, start=1):
        home_price = 1 / match["oh"] if match["oh"] else None
        away_price = 1 / match["oa"] if match["oa"] else None
        current_short_tournament = torneo_corto(match["date"])
        games.append(
            {
                "id": f"mex-{index}",
                "home": match["home"],
                "away": match["away"],
                "home_score": match["hg"],
                "away_score": match["ag"],
                "winner": (
                    HOME if match["hg"] > match["ag"] else AWAY if match["ag"] > match["hg"] else DRAW
                ),
                "kickoff_utc": datetime.combine(match["date"].date(), time(12), tzinfo=UTC),
                "phase": "regular_season",
                "market_home": home_price,
                "market_away": away_price,
                "target": True,
                "rating_regression": (
                    0.80 if current_short_tournament != short_tournament else None
                ),
            }
        )
        short_tournament = current_short_tournament
    return simulate_games(
        "liga_mx_2026",
        games,
        pipeline,
        strategy,
        bankroll=bankroll,
        price_source="football-data.co.uk AvgC closing odds (vig included)",
    )


def _nfl(season: int, bankroll: float) -> dict[str, Any]:
    strategy = load_active_strategy("nfl_2026", require_approved=False)
    assert strategy is not None
    reader = AmericanFootballDBReader("nfl_2026")
    rows = reader.query(
        "SELECT id,home_team_id,away_team_id,home_score,away_score,winner_team_id,"
        "moneyline_home,moneyline_away,week_id,kickoff_utc FROM fixture "
        "WHERE status='finished' AND home_score IS NOT NULL ORDER BY kickoff_utc"
    )
    games = []
    for row in rows:
        home_decimal = (
            american_to_decimal(row["moneyline_home"])
            if row["moneyline_home"] is not None
            else None
        )
        away_decimal = (
            american_to_decimal(row["moneyline_away"])
            if row["moneyline_away"] is not None
            else None
        )
        games.append(
            {
                "id": row["id"],
                "home": row["home_team_id"],
                "away": row["away_team_id"],
                "home_score": int(row["home_score"]),
                "away_score": int(row["away_score"]),
                "winner": (
                    HOME
                    if row["winner_team_id"] == row["home_team_id"]
                    else AWAY if row["winner_team_id"] == row["away_team_id"] else DRAW
                ),
                "kickoff_utc": row["kickoff_utc"],
                "phase": "regular_season",
                "market_home": 1 / home_decimal if home_decimal else None,
                "market_away": 1 / away_decimal if away_decimal else None,
                "target": (row["week_id"] or "").startswith(f"{season}_REG"),
            }
        )
    return simulate_games(
        "nfl_2026",
        games,
        NFLPipeline(),
        strategy,
        bankroll=bankroll,
        price_source="nflverse closing moneyline (vig included)",
    )


def _world_cup(bankroll: float) -> dict[str, Any]:
    strategy = load_active_strategy("fifa_world_cup_2026", require_approved=False)
    assert strategy is not None
    reader = FootballDBReader("fifa_world_cup_2026")
    odds = {
        row["fixture_id"]: row
        for row in reader.query(
            "SELECT fixture_id,home_prob,away_prob FROM polymarket_odds "
            "WHERE source='polymarket'"
        )
    }
    rows = reader.query(
        "SELECT f.*,COALESCE(p.name,'group') phase,p.is_knockout FROM fixture f "
        "LEFT JOIN phase p ON p.id=f.phase_id WHERE f.status='finished' "
        "AND f.home_goals IS NOT NULL ORDER BY f.kickoff_utc"
    )
    games = []
    for row in rows:
        price = odds.get(row["id"], {})
        games.append(
            {
                "id": row["id"],
                "home": row["home_team_id"],
                "away": row["away_team_id"],
                "home_score": int(row["home_goals"]),
                "away_score": int(row["away_goals"]),
                "winner": (
                    HOME
                    if row["home_goals"] > row["away_goals"]
                    else AWAY if row["away_goals"] > row["home_goals"] else DRAW
                ),
                "kickoff_utc": row["kickoff_utc"],
                "phase": "knockout" if row["is_knockout"] else row["phase"],
                "market_home": price.get("home_prob"),
                "market_away": price.get("away_prob"),
                "target": True,
            }
        )
    pipeline = WorldCupPipeline(home_adv_elo=0)
    pipeline.seed(reader.get_seed_elo())
    return simulate_games(
        "fifa_world_cup_2026",
        games,
        pipeline,
        strategy,
        bankroll=bankroll,
        price_source="stored Polymarket pre-match probabilities",
    )


def run(
    tournament_id: str,
    *,
    season: str | None = None,
    bankroll: float = 1000.0,
) -> dict[str, Any]:
    """Despacha el backtest para cualquier torneo registrado soportado."""
    get_config(tournament_id)
    if tournament_id == "liga_mx_2026":
        return _liga_mx(season or "2025/2026", bankroll)
    if tournament_id == "nfl_2026":
        return _nfl(int(season or 2025), bankroll)
    if tournament_id == "fifa_world_cup_2026":
        return _world_cup(bankroll)
    raise ValueError(f"Backtest no implementado para {tournament_id}")
