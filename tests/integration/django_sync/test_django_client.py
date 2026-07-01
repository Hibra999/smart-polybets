"""Tests del DjangoClient con una sesión HTTP falsa (sin red)."""
from __future__ import annotations

import pytest

from core.django_client import DjangoClient
from core.exceptions import DjangoAPIError, NotFoundError


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self.content = b"x" if payload is not None else b""

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.headers = {}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


def _client(response):
    c = DjangoClient(base_url="http://x/api/agent", api_key="k")
    c.session = FakeSession(response)
    return c


def test_get_portfolio_state():
    c = _client(FakeResponse(200, {"bankroll_usdc": "1000"}))
    assert c.get_portfolio_state() == {"bankroll_usdc": "1000"}


def test_check_idempotency_returns_none_on_404():
    c = _client(FakeResponse(404))
    assert c.check_idempotency("key") is None


def test_error_raises_django_api_error():
    c = _client(FakeResponse(500, {"err": 1}, text="boom"))
    with pytest.raises(DjangoAPIError):
        c.get_portfolio_state()


def test_not_found_raises():
    c = _client(FakeResponse(404))
    with pytest.raises(NotFoundError):
        c.get_portfolio_state()


def test_save_decision_posts():
    c = _client(FakeResponse(201, {"id": 1, "idempotency_key": "k"}))
    out = c.save_decision({"idempotency_key": "k"})
    assert out["id"] == 1
    method, url, _ = c.session.calls[0]
    assert method == "POST"
    assert url.endswith("/decisions/")
