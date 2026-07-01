"""Join en Python entre torneos del mismo deporte (fútbol).

No es SQL — es semántica deportiva. Itera múltiples FootballDBReader (uno por
torneo) y combina los resultados en memoria.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from adapters.football.db_reader import FootballDBReader


class FootballCrossTournamentJoiner:
    """Combina datos de varios torneos de fútbol registrados localmente."""

    def __init__(self, *, connections: dict[str, sqlite3.Connection] | None = None) -> None:
        # `connections` permite inyectar conexiones por torneo (tests). En
        # producción se resuelven las rutas de cada torneo.
        self._connections = connections or {}

    def _reader(self, tournament_id: str) -> FootballDBReader:
        conn = self._connections.get(tournament_id)
        return FootballDBReader(tournament_id, connection=conn)

    def get_player_cross_tournament_stats(
        self, player_id: str, tournament_ids: list[str]
    ) -> dict[str, Any]:
        """Estadísticas agregadas de un jugador en múltiples torneos.

        Útil para: "¿cómo le va a Messi en partidos de eliminación directa?"
        """
        per_tournament: dict[str, dict] = {}
        totals = {"goals": 0, "assists": 0, "minutes_played": 0, "matches": 0}
        for tid in tournament_ids:
            reader = self._reader(tid)
            rows = reader.query(
                """
                SELECT COUNT(*) AS matches,
                       COALESCE(SUM(goals), 0) AS goals,
                       COALESCE(SUM(assists), 0) AS assists,
                       COALESCE(SUM(minutes_played), 0) AS minutes_played
                FROM match_player_stat WHERE player_id = ?
                """,
                (player_id,),
            )
            agg = rows[0] if rows else {}
            per_tournament[tid] = agg
            for k in totals:
                totals[k] += int(agg.get(k) or 0)
        return {"player_id": player_id, "per_tournament": per_tournament, "totals": totals}

    def get_team_historical_elo(
        self, team_id: str, tournament_ids: list[str]
    ) -> list[dict]:
        """Serie Elo de un equipo a través de múltiples torneos (orden temporal)."""
        series: list[dict] = []
        for tid in tournament_ids:
            reader = self._reader(tid)
            for row in reader.get_elo_history(team_id):
                row["tournament_id"] = tid
                series.append(row)
        series.sort(key=lambda r: (r.get("rated_at") or ""))
        return series

    def get_h2h_across_tournaments(
        self, team_a: str, team_b: str, tournament_ids: list[str]
    ) -> list[dict]:
        """Head-to-head histórico entre dos equipos en cualquier torneo registrado."""
        all_matches: list[dict] = []
        for tid in tournament_ids:
            reader = self._reader(tid)
            for m in reader.get_head_to_head(team_a, team_b, limit=100):
                m["tournament_id"] = tid
                all_matches.append(m)
        all_matches.sort(key=lambda r: (r.get("kickoff_utc") or ""), reverse=True)
        return all_matches
