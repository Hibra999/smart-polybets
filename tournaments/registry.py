"""Registro global de torneos: {tournament_id → TournamentConfig}.

Agregar un torneo nuevo = agregar una entrada acá + su carpeta de estrategias +
su SQLite. El pipeline de áreas no cambia (whitepaper sección 13).

También resuelve:
  - `get_adapter(tournament_id)` → instancia del SportAdapter del torneo
  - `load_active_strategy(tournament_id)` → StrategyConfig aprobada (o None)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from adapters.base import SportAdapter
from core.exceptions import NotFoundError
from core.strategy import StrategyConfig, parse_strategy_md

TOURNAMENTS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class TournamentConfig:
    tournament_id: str
    display_name: str
    sport: str
    adapter_factory: Callable[[str], SportAdapter]
    active_strategy: str  # path relativo a tournaments/, ej: "fifa_world_cup_2026/strategies/match_winner_v1"
    start_date: str
    end_date: str
    # ── parámetros de venue/modelo por torneo (aditivos; defaults = Mundial) ──
    polymarket_tag_id: int | None = None  # tag de PM para discovery/update_results
    neutral_venue: bool = True            # False = liga con localía (Poisson neutral=False)
    home_adv_elo: float = 0.0             # puntos Elo de localía (0 = sede neutral)


def _football_worldcup(tournament_id: str) -> SportAdapter:
    # Adapter Elo+Bayes evolutivo (migrado de pypro_worldcup_betting). La ventaja
    # de localía sale de la config del torneo (0 para el Mundial: sede neutral).
    from adapters.football.worldcup_adapter import FootballWorldCupAdapter
    cfg = TOURNAMENTS[tournament_id]
    return FootballWorldCupAdapter(tournament_id, home_adv_elo=cfg.home_adv_elo)


def _nfl_trueskill(tournament_id: str) -> SportAdapter:
    # Modelo migrado de sports_bet: TrueSkill evolutivo sobre los juegos jugados.
    from adapters.american_football.trueskill_loader import AmericanFootballTrueSkillAdapter
    return AmericanFootballTrueSkillAdapter(tournament_id)


TOURNAMENTS: dict[str, TournamentConfig] = {
    "liga_mx_2026": TournamentConfig(
        tournament_id="liga_mx_2026",
        display_name="Liga MX Apertura 2026",
        sport="football",
        adapter_factory=_football_worldcup,
        active_strategy="liga_mx_2026/strategies/match_winner_ligamx_v1",
        start_date="2026-07-16",
        end_date="2026-12-13",
        polymarket_tag_id=102448,
        neutral_venue=False,
        # CALIBRADO 2026-07-14: grid search sobre 2022/23-2025/26 (football-data
        # MEX.csv), Brier 0.15940 en el óptimo. Ver scripts/ligamx_backtest.py y
        # docs/findings/2026-07-14-ligamx-backtest.md.
        home_adv_elo=80.0,
    ),
    "fifa_world_cup_2026": TournamentConfig(
        tournament_id="fifa_world_cup_2026",
        display_name="FIFA World Cup 2026",
        sport="football",
        adapter_factory=_football_worldcup,
        active_strategy="fifa_world_cup_2026/strategies/match_winner_wc_v1",
        start_date="2026-06-11",
        end_date="2026-07-19",
        polymarket_tag_id=102232,
        neutral_venue=True,
        home_adv_elo=0.0,
    ),
    "nfl_2026": TournamentConfig(
        tournament_id="nfl_2026",
        display_name="NFL 2026 Season",
        sport="american_football",
        adapter_factory=_nfl_trueskill,
        active_strategy="nfl_2026/strategies/game_winner_v1",
        start_date="2026-09-06",
        end_date="2027-02-08",
    ),
}


def get_config(tournament_id: str) -> TournamentConfig:
    try:
        return TOURNAMENTS[tournament_id]
    except KeyError as exc:
        raise NotFoundError(f"Torneo no registrado: {tournament_id}") from exc


def get_adapter(tournament_id: str) -> SportAdapter:
    """Instancia el SportAdapter del torneo según su config."""
    return get_config(tournament_id).adapter_factory(tournament_id)


def load_strategy_file(rel_path: str) -> StrategyConfig:
    """Parsea un STRATEGY.md dado su path relativo a tournaments/."""
    strategy_id = Path(rel_path).name
    path = TOURNAMENTS_DIR / rel_path / "STRATEGY.md"
    if not path.exists():
        raise NotFoundError(f"STRATEGY.md no encontrado: {path}")
    text = path.read_text(encoding="utf-8")
    return parse_strategy_md(text, strategy_id=strategy_id, source_path=str(path))


def load_active_strategy(
    tournament_id: str, *, require_approved: bool = True
) -> StrategyConfig | None:
    """StrategyConfig de la estrategia activa del torneo.

    Si `require_approved` y la estrategia no está en status=approved, retorna None
    (el workflow PIPELINE lo trata como "no hay estrategia aprobada").
    """
    cfg = get_config(tournament_id)
    strategy = load_strategy_file(cfg.active_strategy)
    if require_approved and not strategy.is_approved:
        return None
    return strategy
