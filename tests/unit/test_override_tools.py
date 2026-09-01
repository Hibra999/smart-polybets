"""Tests del carril CIO-override (agent/tools/override_tools.py).

Contratos:
  - un override que pasa riesgo queda como Decision REVIEW (nunca AUTO) con el
    stake del CIO y la razón en el ledger;
  - un DISCARD del motor de riesgo bloquea sin persistir nada;
  - la idempotencia impide proponer dos veces la misma apuesta el mismo día;
  - `reason` es obligatoria (auditoría).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from agent.tools.override_tools import propose_override
from tests.conftest import FakeLocalStateClient, make_opportunity
from tournaments.registry import load_strategy_file

STRATEGY = load_strategy_file("liga_mx_2026/strategies/match_winner_ligamx_v1")


def _opp(**kw):
    return make_opportunity(**kw)


def test_override_saves_review_with_cio_stake():
    client = FakeLocalStateClient()
    res = propose_override(_opp(), stake_usdc=Decimal("12"), reason="Poisson vs ask",
                           client=client, strategy=STRATEGY)
    assert res["mode"] == "REVIEW"
    assert len(client.saved) == 1
    payload = client.saved[0]
    assert payload["status"] == "pending_approval"          # nunca AUTO
    assert payload["verdict"] == "REVIEW"
    assert Decimal(payload["recommended_size"]) == Decimal("12")  # stake del CIO, no Kelly
    assert any("CIO override" in r for r in payload["risk_verdict_json"]["reasons"])
    assert not client.executed                              # proponer NO coloca


def test_override_discard_blocks_without_saving():
    client = FakeLocalStateClient()
    # edge negativo → DISCARD del motor de riesgo (control que la ruta manual no tenía)
    res = propose_override(_opp(model_probability="0.30", market_probability="0.60"),
                           stake_usdc=Decimal("12"), reason="apuesta caprichosa",
                           client=client, strategy=STRATEGY)
    assert res["mode"] == "DISCARD"
    assert res["blocking_rules"]
    assert not client.saved


def test_override_idempotent_same_day():
    class Client(FakeLocalStateClient):
        def __init__(self):
            super().__init__()
            self._by_key = {}

        def save_decision(self, payload):
            self._by_key[payload["idempotency_key"]] = payload
            return super().save_decision(payload)

        def check_idempotency(self, key):
            return self._by_key.get(key)

    client = Client()
    opp = _opp()
    first = propose_override(opp, stake_usdc=Decimal("12"), reason="r",
                             client=client, strategy=STRATEGY)
    second = propose_override(opp, stake_usdc=Decimal("99"), reason="r2",
                              client=client, strategy=STRATEGY)
    assert first["mode"] == "REVIEW"
    assert second["mode"] == "SKIP"
    assert len(client.saved) == 1


def test_override_requires_reason_and_positive_stake():
    client = FakeLocalStateClient()
    with pytest.raises(ValueError):
        propose_override(_opp(), stake_usdc=Decimal("12"), reason="  ",
                         client=client, strategy=STRATEGY)
    with pytest.raises(ValueError):
        propose_override(_opp(), stake_usdc=Decimal("0"), reason="r",
                         client=client, strategy=STRATEGY)
