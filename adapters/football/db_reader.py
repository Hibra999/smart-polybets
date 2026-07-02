"""Queries canónicas sobre el schema football.sql.

Agnóstico al torneo — recibe tournament_id. Sin lógica de negocio: sólo acceso a
datos, read-only.
"""
from __future__ import annotations

from typing import Any

from adapters.base import SQLiteReader
from core.utils import utcnow


class FootballDBReader(SQLiteReader):
    """Lector read-only del SQLite de un torneo de fútbol asociación."""

    def get_fixture(self, fixture_id: str) -> dict[str, Any] | None:
        """Partido con nombres de equipos y nombre de fase."""
        return self.query_one(
            """
            SELECT f.*,
                   ht.name AS home_team_name,
                   at.name AS away_team_name,
                   p.name  AS phase_name,
                   p.is_knockout AS phase_is_knockout
            FROM fixture f
            LEFT JOIN team ht ON ht.id = f.home_team_id
            LEFT JOIN team at ON at.id = f.away_team_id
            LEFT JOIN phase p ON p.id = f.phase_id
            WHERE f.id = ?
            """,
            (fixture_id,),
        )

    def get_upcoming_fixtures(self, hours_ahead: int = 24, *, now: Any = None) -> list[dict]:
        """Partidos programados en las próximas N horas."""
        ref_iso = (now or utcnow()).isoformat()
        # Normalizar AMBOS lados con datetime() de SQLite: así la comparación es sobre el
        # formato canónico ('YYYY-MM-DD HH:MM:SS' en UTC) y no una comparación de strings
        # frágil entre ISO-con-'T'+tz y la salida-con-espacio de datetime() (que fallaba
        # según la hora del día cuando compartían fecha).
        return self.query(
            """
            SELECT * FROM fixture
            WHERE status = 'scheduled'
              AND datetime(kickoff_utc) >= datetime(?)
              AND datetime(kickoff_utc) <= datetime(?, ?)
            ORDER BY kickoff_utc ASC
            """,
            (ref_iso, ref_iso, f"+{int(hours_ahead)} hours"),
        )

    def get_team(self, team_id: str) -> dict[str, Any] | None:
        """Equipo con su Elo actual y contexto."""
        return self.query_one("SELECT * FROM team WHERE id = ?", (team_id,))

    def get_squad(self, team_id: str) -> list[dict]:
        """Plantel del equipo con status de disponibilidad."""
        return self.query(
            "SELECT * FROM player WHERE team_id = ? ORDER BY jersey_number", (team_id,)
        )

    def get_player_availability(self, team_id: str) -> list[dict]:
        """Jugadores del equipo con status != 'available' (lesionados/suspendidos)."""
        return self.query(
            """
            SELECT p.id AS player_id, p.name, p.position, pa.status, pa.reason,
                   pa.reported_at, pa.expected_return, pa.source
            FROM player p
            JOIN player_availability pa ON pa.player_id = p.id
            WHERE p.team_id = ? AND pa.status != 'available'
            ORDER BY pa.reported_at DESC
            """,
            (team_id,),
        )

    def get_head_to_head(self, team_a: str, team_b: str, limit: int = 10) -> list[dict]:
        """Últimos N partidos entre dos equipos (en este torneo)."""
        return self.query(
            """
            SELECT * FROM fixture
            WHERE status = 'finished'
              AND ((home_team_id = ? AND away_team_id = ?)
                OR (home_team_id = ? AND away_team_id = ?))
            ORDER BY kickoff_utc DESC
            LIMIT ?
            """,
            (team_a, team_b, team_b, team_a, limit),
        )

    def get_team_form(self, team_id: str, last_n: int = 5) -> list[dict]:
        """Últimos N partidos terminados del equipo, con resultado."""
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

    def get_elo_history(self, team_id: str) -> list[dict]:
        """Serie histórica de ratings Elo del equipo."""
        return self.query(
            """
            SELECT * FROM elo_rating_history
            WHERE team_id = ?
            ORDER BY rated_at ASC
            """,
            (team_id,),
        )

    def get_teams(self) -> list[dict]:
        """Todos los equipos del torneo con su Elo inicial."""
        return self.query("SELECT * FROM team ORDER BY id")

    def get_seed_elo(self) -> dict[str, float]:
        """{team_id → elo_rating inicial} para sembrar el pipeline Elo/Bayes."""
        return {
            t["id"]: float(t["elo_rating"])
            for t in self.get_teams()
            if t.get("elo_rating") is not None
        }

    def get_finished_fixtures(self, *, before_utc: str | None = None) -> list[dict]:
        """Partidos terminados en orden cronológico (para evolucionar los modelos).

        Si `before_utc` se pasa, sólo devuelve los jugados antes de ese instante
        (para no filtrar el propio partido objetivo ni los posteriores).
        """
        if before_utc is not None:
            return self.query(
                """
                SELECT * FROM fixture
                WHERE status = 'finished'
                  AND home_goals IS NOT NULL AND away_goals IS NOT NULL
                  AND kickoff_utc < ?
                ORDER BY kickoff_utc ASC
                """,
                (before_utc,),
            )
        return self.query(
            """
            SELECT * FROM fixture
            WHERE status = 'finished'
              AND home_goals IS NOT NULL AND away_goals IS NOT NULL
            ORDER BY kickoff_utc ASC
            """
        )

    def get_standing(self, group_id: str | None = None) -> list[dict]:
        """Tabla de posiciones (standing actual: matchday NULL), opcional por grupo."""
        if group_id is not None:
            return self.query(
                """
                SELECT * FROM standing
                WHERE group_id = ? AND matchday IS NULL
                ORDER BY position ASC
                """,
                (group_id,),
            )
        return self.query(
            "SELECT * FROM standing WHERE matchday IS NULL ORDER BY position ASC"
        )
