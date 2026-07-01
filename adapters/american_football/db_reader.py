"""Queries canónicas sobre el schema american_football.sql. Read-only."""
from __future__ import annotations

from typing import Any

from adapters.base import SQLiteReader
from core.utils import utcnow


class AmericanFootballDBReader(SQLiteReader):
    """Lector read-only del SQLite de una temporada NFL."""

    def get_game(self, game_id: str) -> dict[str, Any] | None:
        return self.query_one(
            """
            SELECT f.*,
                   ht.name AS home_team_name,
                   at.name AS away_team_name,
                   w.phase AS week_phase
            FROM fixture f
            LEFT JOIN team ht ON ht.id = f.home_team_id
            LEFT JOIN team at ON at.id = f.away_team_id
            LEFT JOIN week w ON w.id = f.week_id
            WHERE f.id = ?
            """,
            (game_id,),
        )

    def get_upcoming_games(self, hours_ahead: int = 72, *, now: Any = None) -> list[dict]:
        ref = now or utcnow()
        return self.query(
            """
            SELECT * FROM fixture
            WHERE status = 'scheduled'
              AND kickoff_utc >= ?
              AND kickoff_utc <= datetime(?, ?)
            ORDER BY kickoff_utc ASC
            """,
            (ref.isoformat(), ref.isoformat(), f"+{int(hours_ahead)} hours"),
        )

    def get_team(self, team_id: str) -> dict[str, Any] | None:
        return self.query_one("SELECT * FROM team WHERE id = ?", (team_id,))

    def get_roster(self, team_id: str) -> list[dict]:
        return self.query(
            "SELECT * FROM player WHERE team_id = ? ORDER BY depth_chart_rank", (team_id,)
        )

    def get_injury_report(self, team_id: str) -> list[dict]:
        """Injury report de los jugadores del equipo (status != probable)."""
        return self.query(
            """
            SELECT ir.*, p.name, p.position
            FROM injury_report ir
            JOIN player p ON p.id = ir.player_id
            WHERE p.team_id = ?
              AND (ir.game_status IS NOT NULL AND ir.game_status != '')
            ORDER BY ir.reported_at DESC
            """,
            (team_id,),
        )

    def get_team_form(self, team_id: str, last_n: int = 5) -> list[dict]:
        return self.query(
            """
            SELECT * FROM fixture
            WHERE status = 'finished'
              AND (home_team_id = ? OR away_team_id = ?)
            ORDER BY kickoff_utc DESC
            LIMIT ?
            """,
            (team_id, team_id, last_n),
        )

    def get_teams(self) -> list[dict]:
        """Todas las franquicias del torneo."""
        return self.query("SELECT * FROM team ORDER BY id")

    def get_finished_fixtures(self, *, before_utc: str | None = None) -> list[dict]:
        """Partidos terminados en orden cronológico (para evolucionar TrueSkill).

        Si `before_utc`, sólo los jugados antes de ese instante (no filtra el
        propio partido objetivo ni los posteriores).
        """
        if before_utc is not None:
            return self.query(
                """
                SELECT * FROM fixture
                WHERE status = 'finished'
                  AND home_score IS NOT NULL AND away_score IS NOT NULL
                  AND kickoff_utc < ?
                ORDER BY kickoff_utc ASC
                """,
                (before_utc,),
            )
        return self.query(
            """
            SELECT * FROM fixture
            WHERE status = 'finished'
              AND home_score IS NOT NULL AND away_score IS NOT NULL
            ORDER BY kickoff_utc ASC
            """
        )

    def get_standing(self, week_id: str | None = None) -> list[dict]:
        if week_id is not None:
            return self.query(
                "SELECT * FROM standing WHERE week_id = ? ORDER BY div_rank ASC", (week_id,)
            )
        return self.query("SELECT * FROM standing ORDER BY div_rank ASC")
