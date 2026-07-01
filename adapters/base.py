"""Base de la capa de adapters.

- `SportAdapter` (alias `SportDataAdapter`): ABC que produce predicciones del
  modelo de un torneo. Research lo consume vía model_loader.
- `SQLiteReader`: helper read-only compartido por los db_readers de cada deporte.

Regla: esta capa NUNCA escribe en el SQLite. Si el archivo no existe →
FileNotFoundError inmediato, no silencioso.
"""
from __future__ import annotations

import os
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from core.exceptions import AdapterError


def get_db_path(tournament_id: str, data_root: str | os.PathLike | None = None) -> Path:
    """Ruta canónica del SQLite de un torneo: data/{id}/{id}.sqlite."""
    root = Path(data_root or os.getenv("DATA_ROOT", "data"))
    return root / tournament_id / f"{tournament_id}.sqlite"


class SQLiteReader:
    """Acceso de sólo lectura a un SQLite de torneo.

    Para tests, se puede inyectar una conexión existente (ej: :memory:) vía
    `connection`. En producción se resuelve la ruta del torneo y se abre en modo
    read-only (URI `mode=ro`).
    """

    def __init__(
        self,
        tournament_id: str,
        *,
        connection: sqlite3.Connection | None = None,
        data_root: str | os.PathLike | None = None,
    ) -> None:
        self.tournament_id = tournament_id
        self._external_conn = connection is not None
        if connection is not None:
            self._conn = connection
            self._conn.row_factory = sqlite3.Row
            self.db_path = None
            return

        self.db_path = get_db_path(tournament_id, data_root)
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite no encontrado: {self.db_path}")
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        self._conn = sqlite3.connect(uri, uri=True)
        self._conn.row_factory = sqlite3.Row

    # ── helpers ──────────────────────────────────────────────────────────────

    def query(self, sql: str, params: tuple | dict = ()) -> list[dict[str, Any]]:
        try:
            cur = self._conn.execute(sql, params)
        except sqlite3.Error as exc:
            raise AdapterError(f"Error de query en {self.tournament_id}: {exc}") from exc
        return [dict(row) for row in cur.fetchall()]

    def query_one(self, sql: str, params: tuple | dict = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def close(self) -> None:
        if not self._external_conn:
            self._conn.close()

    def __enter__(self) -> "SQLiteReader":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class SportAdapter(ABC):
    """Contrato de un adapter de modelo deportivo.

    Cada deporte/torneo implementa cómo cargar la predicción de un evento desde
    sus modelos (Elo/Bayes/TrueSkill del repo del torneo).
    """

    sport: str

    @abstractmethod
    def get_event_prediction(self, event_id: str) -> Any:
        """Retorna un MatchPrediction para el evento, o None si no hay predicción."""
        raise NotImplementedError


# Alias por compatibilidad con el whitepaper (sección 4: "SportDataAdapter ABC").
SportDataAdapter = SportAdapter
