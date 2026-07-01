"""Cliente HTTP repo → Django App.

El repo NUNCA escribe directamente a la base de datos: toda operación que
necesita estado pasa por aquí. El Django App es la única fuente de verdad del
estado (posiciones, bankroll, decisiones, aprobaciones).

Si el Django App está caído, las operaciones levantan DjangoAPIError y el
workflow PARA — no continúa con estado stale.
"""
from __future__ import annotations

import os
from typing import Any

import requests

from core.exceptions import DjangoAPIError, NotFoundError

DJANGO_API_BASE = os.getenv("DJANGO_API_BASE", "http://localhost:8000/api/agent")
DJANGO_API_KEY = os.getenv("DJANGO_API_KEY")  # token interno de servicio, no de usuario

DEFAULT_TIMEOUT = 10  # segundos


class DjangoClient:
    """Cliente del API interno `/api/agent/` del Django App."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 timeout: int = DEFAULT_TIMEOUT) -> None:
        self.base_url = (base_url or DJANGO_API_BASE).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Token {api_key or DJANGO_API_KEY}",
                "Content-Type": "application/json",
            }
        )

    # ── Helpers HTTP ─────────────────────────────────────────────────────────

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            resp = self.session.request(
                method, self._url(path), timeout=self.timeout, **kwargs
            )
        except requests.RequestException as exc:
            raise DjangoAPIError(f"Django App inalcanzable: {exc}") from exc

        if resp.status_code == 404:
            raise NotFoundError(f"{method} {path} → 404")
        if not resp.ok:
            raise DjangoAPIError(
                f"{method} {path} → {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def _get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def _post(self, path: str, payload: dict) -> Any:
        return self._request("POST", path, json=payload)

    def _patch(self, path: str, payload: dict) -> Any:
        return self._request("PATCH", path, json=payload)

    # ── Lectura de estado ────────────────────────────────────────────────────

    def get_portfolio_state(self) -> dict:
        """Estado actual: posiciones abiertas, bankroll, drawdown."""
        return self._get("/portfolio/state/")

    def get_active_tournaments(self) -> list[dict]:
        """Torneos registrados con status=active en el Django App."""
        return self._get("/tournaments/active/")

    def check_idempotency(self, idempotency_key: str) -> dict | None:
        """Retorna el DecisionLog existente o None si es nuevo."""
        try:
            return self._get(f"/decisions/{idempotency_key}/")
        except NotFoundError:
            return None

    def get_open_positions(self, tournament_id: str | None = None) -> list[dict]:
        """Posiciones abiertas, opcionalmente filtradas por torneo."""
        params = {"tournament_id": tournament_id} if tournament_id else None
        return self._get("/positions/open/", params=params)

    def get_exposure_by_participant(self, tournament_id: str) -> dict:
        """Exposición por equipo/jugador — para el constraint de risk."""
        return self._get(f"/tournaments/{tournament_id}/exposure/")

    # ── Escritura de estado ──────────────────────────────────────────────────

    def save_decision(self, decision_payload: dict) -> dict:
        """Persiste un AgentDecisionLog nuevo. El Django valida idempotency_key."""
        return self._post("/decisions/", decision_payload)

    def mark_executed(self, idempotency_key: str, order_result: dict) -> dict:
        """Actualiza status=executed y linkea el Trade resultante."""
        return self._patch(f"/decisions/{idempotency_key}/execute/", order_result)

    def mark_approved(self, idempotency_key: str, approved_by: str = "human") -> dict:
        """Marca un REVIEW como aprobado. El Django valida que esté pending."""
        return self._patch(
            f"/decisions/{idempotency_key}/approve/", {"approved_by": approved_by}
        )

    def mark_rejected(self, idempotency_key: str, reason: str) -> dict:
        """Rechaza un REVIEW."""
        return self._patch(f"/decisions/{idempotency_key}/reject/", {"reason": reason})

    def register_tournament(self, tournament_config: dict) -> dict:
        """Registra un torneo nuevo en el Django App."""
        return self._post("/tournaments/", tournament_config)

    # ── Sync de wallet ───────────────────────────────────────────────────────

    def trigger_wallet_sync(self) -> dict:
        """Dispara el sync de la wallet de Polymarket (Celery task en Django)."""
        return self._post("/sync/trigger/", {})

    def get_sync_status(self) -> dict:
        return self._get("/sync/status/")

    def get_trade_by_condition(self, condition_id: str, outcome: str) -> dict | None:
        """Busca un trade ejecutado por condition_id + outcome."""
        try:
            return self._get(
                "/trades/", params={"condition_id": condition_id, "outcome": outcome}
            )
        except NotFoundError:
            return None
