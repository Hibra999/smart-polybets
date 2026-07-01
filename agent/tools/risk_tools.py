"""Tools de Risk para el agente."""
from __future__ import annotations

from core.strategy import StrategyConfig
from portfolio.schemas.portfolio_state import PortfolioState
from research.schemas.market_opportunity import MarketOpportunity
from risk.functions import evaluate as _evaluate
from risk.schemas.risk_verdict import RiskVerdict


def evaluate(
    opportunity: MarketOpportunity,
    strategy: StrategyConfig,
    portfolio_state: PortfolioState,
    *,
    qualitative_flags: list[str] | None = None,
) -> RiskVerdict:
    return _evaluate(
        opportunity, strategy, portfolio_state, qualitative_flags=qualitative_flags
    )


def qualitative_flags_for_football(
    tournament_id: str, home_team_id: str, away_team_id: str
) -> list[str]:
    """Calcula flags cualitativos desde los adapters (ej: QR-002 por lesiones).

    Si hay jugadores con status != available en cualquiera de los dos equipos,
    activa QR-002 (cambios/lesiones). Los datos son best-effort (ver adapters/SKILL.md).
    """
    from adapters.football.db_reader import FootballDBReader

    reader = FootballDBReader(tournament_id)
    flags: list[str] = []
    for team_id in (home_team_id, away_team_id):
        unavailable = reader.get_player_availability(team_id)
        if unavailable:
            names = ", ".join(u.get("name", u.get("player_id", "?")) for u in unavailable[:3])
            flags.append(f"QR-002: bajas/dudas en {team_id} ({names})")
    return flags
