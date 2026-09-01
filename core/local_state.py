"""Backend de estado local persistido en JSON.

Implementa la interfaz que usa el pipeline (get_portfolio_state,
check_idempotency, save_decision, mark_executed, get_active_tournaments) pero
persiste en un JSON local. Sirve para operar de forma autónoma sin levantar el
Garantiza **idempotencia** (no doble-apostar) y registra decisiones/ejecuciones.
El bankroll es un parámetro que debe reconciliarse con la wallet real.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from core.utils import utcnow


class LocalStateClient:
    """Estado de trading persistido en un archivo JSON local."""

    def __init__(self, path: str | Path = "data/agent_state.json",
                 bankroll_usdc: float = 1000.0) -> None:
        self.path = Path(path)
        self._state = self._load()
        stored = self._state.get("bankroll_usdc")
        self.initial_bankroll = Decimal(str(stored if stored is not None else bankroll_usdc))

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {"decisions": {}}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state, indent=2, default=str), encoding="utf-8")

    # ── interfaz consumida por el pipeline ───────────────────────────────────

    def get_portfolio_state(self) -> dict:
        executed = [d for d in self._state["decisions"].values()
                    if d.get("status") == "executed"]
        staked = sum(Decimal(str(d.get("recommended_size", 0))) for d in executed)
        exposure: dict[str, Decimal] = {}
        for d in executed:
            part = (d.get("opportunity_json") or {}).get("participant_home", "?")
            exposure[part] = exposure.get(part, Decimal(0)) + Decimal(str(d.get("recommended_size", 0)))
        bankroll = self.initial_bankroll
        return {
            "bankroll_usdc": str(bankroll),
            "drawdown_7d": "0",
            "open_positions": [],
            "exposure_by_participant": {
                k: str(v / bankroll) if bankroll else "0" for k, v in exposure.items()
            },
            "as_of": utcnow().isoformat(),
            "_staked_usdc": str(staked),
        }

    def check_idempotency(self, idempotency_key: str) -> dict | None:
        return self._state["decisions"].get(idempotency_key)

    def save_decision(self, payload: dict[str, Any]) -> dict:
        key = payload["idempotency_key"]
        # No pisar una decisión ya ejecutada (idempotencia dura).
        if key not in self._state["decisions"]:
            self._state["decisions"][key] = {**payload, "saved_at": utcnow().isoformat()}
            self._save()
        return self._state["decisions"][key]

    def mark_executed(self, idempotency_key: str, order_result: dict) -> dict:
        d = self._state["decisions"].setdefault(idempotency_key, {"idempotency_key": idempotency_key})
        d["status"] = "executed"
        d["order_result"] = order_result
        d["executed_at"] = utcnow().isoformat()
        self._save()
        return d

    def mark_simulated(self, idempotency_key: str, order_result: dict) -> dict:
        """Registra un dry-run SIN marcar ejecutado: status `simulated` no bloquea
        la idempotencia (el run real siguiente puede reprocesar la decisión)."""
        d = self._state["decisions"].setdefault(idempotency_key, {"idempotency_key": idempotency_key})
        d["status"] = "simulated"
        d["order_result"] = order_result
        d["simulated_at"] = utcnow().isoformat()
        self._save()
        return d

    def set_bankroll(self, value: Decimal | float) -> dict:
        """Persiste el bankroll (p. ej. tras reconciliar con el balance real)."""
        self._state["bankroll_usdc"] = str(value)
        self.initial_bankroll = Decimal(str(value))
        self._save()
        return {"bankroll_usdc": self._state["bankroll_usdc"]}

    def get_exposure_by_participant(self, tournament_id: str) -> dict:
        """Exposición por participante (ratio sobre bankroll) para el torneo dado."""
        state = self.get_portfolio_state()
        return state.get("exposure_by_participant", {})

    def get_active_tournaments(self) -> list[dict]:
        return [
            {"tournament_id": "liga_mx_2026"},
            {"tournament_id": "nfl_2026"},
        ]
