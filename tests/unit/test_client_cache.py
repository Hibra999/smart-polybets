"""Tests para la caché de clientes del SDK de Polymarket (sin red).

Verifica que `build_secure_client` y `build_public_client` devuelven la MISMA
instancia para los mismos parámetros dentro del proceso, y que `SecureClient.create`
/ `PublicClient.__init__` solo se llaman UNA vez.

Usa monkeypatch en sys.modules para evitar depender del SDK real.
"""
from __future__ import annotations

import sys
import types

import pytest

from core.polymarket_client import (
    build_public_client,
    build_secure_client,
    reset_client_cache,
)

# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_cache():
    """Limpia la caché antes y después de cada test."""
    reset_client_cache()
    yield
    reset_client_cache()


def _inject_fake_polymarket(monkeypatch, calls: list):
    """Inyecta un módulo `polymarket` falso con un SecureClient que registra llamadas."""

    class FakeRelayerApiKey:
        def __init__(self, *, key, address):
            self.key = key
            self.address = address

    class FakeSecureClient:
        @classmethod
        def create(cls, **kwargs):
            instance = object()
            calls.append({"kwargs": kwargs, "instance": instance})
            return instance

    fake_mod = types.ModuleType("polymarket")
    fake_mod.SecureClient = FakeSecureClient
    fake_mod.RelayerApiKey = FakeRelayerApiKey
    monkeypatch.setitem(sys.modules, "polymarket", fake_mod)
    return FakeSecureClient


def _inject_fake_public_client(monkeypatch, calls: list):
    """Inyecta módulos falsos para polymarket.clients.public con PublicClient."""

    class FakePublicClient:
        def __init__(self):
            calls.append(True)

    fake_pub_mod = types.ModuleType("polymarket.clients.public")
    fake_pub_mod.PublicClient = FakePublicClient

    fake_clients_mod = types.ModuleType("polymarket.clients")
    fake_clients_mod.public = fake_pub_mod

    fake_poly_mod = types.ModuleType("polymarket")
    fake_poly_mod.clients = fake_clients_mod

    monkeypatch.setitem(sys.modules, "polymarket", fake_poly_mod)
    monkeypatch.setitem(sys.modules, "polymarket.clients", fake_clients_mod)
    monkeypatch.setitem(sys.modules, "polymarket.clients.public", fake_pub_mod)
    return FakePublicClient


# ── tests SecureClient cache ──────────────────────────────────────────────────


def test_same_key_returns_cached_instance(monkeypatch):
    """Dos llamadas con la misma private_key devuelven el MISMO objeto."""
    calls: list = []
    _inject_fake_polymarket(monkeypatch, calls)

    c1 = build_secure_client(private_key="0xabc")
    c2 = build_secure_client(private_key="0xabc")

    assert c1 is c2, "Segunda llamada debe devolver el objeto cacheado"
    assert len(calls) == 1, "SecureClient.create solo debe llamarse UNA vez"


def test_different_key_returns_different_instance(monkeypatch):
    """Una tercera llamada con diferente key crea un nuevo cliente."""
    calls: list = []
    _inject_fake_polymarket(monkeypatch, calls)

    c1 = build_secure_client(private_key="0xabc")
    c2 = build_secure_client(private_key="0xabc")
    c3 = build_secure_client(private_key="0xdef")

    assert c1 is c2
    assert c3 is not c1, "Key distinta debe producir instancia diferente"
    assert len(calls) == 2, "SecureClient.create debe haberse llamado exactamente DOS veces"


def test_key_prefix_normalised_shares_cache(monkeypatch):
    """'abc' y '0xabc' (después de normalizar) apuntan al mismo caché."""
    calls: list = []
    _inject_fake_polymarket(monkeypatch, calls)

    c1 = build_secure_client(private_key="0xabc")
    c2 = build_secure_client(private_key="abc")  # sin prefijo 0x → normalizado

    assert c1 is c2
    assert len(calls) == 1


def test_same_key_different_funder_is_separate_cache_entry(monkeypatch):
    """La misma key con diferente funder debe dar instancias distintas."""
    calls: list = []
    _inject_fake_polymarket(monkeypatch, calls)

    c1 = build_secure_client(private_key="0xabc", funder="0xWALLET1")
    c2 = build_secure_client(private_key="0xabc", funder="0xWALLET2")

    assert c1 is not c2
    assert len(calls) == 2


def test_relayer_credentials_are_forwarded_without_replacing_signer(monkeypatch):
    calls: list = []
    _inject_fake_polymarket(monkeypatch, calls)

    build_secure_client(
        private_key="0xabc",
        relayer_api_key="relayer-key",
        relayer_api_key_address="0x30a886Ac66Ba6ad8cc61Db95ae72f63091Bb4e9b",
    )

    kwargs = calls[0]["kwargs"]
    assert kwargs["private_key"] == "0xabc"
    assert kwargs["api_key"].key == "relayer-key"
    assert kwargs["api_key"].address == "0x30a886Ac66Ba6ad8cc61Db95ae72f63091Bb4e9b"


def test_failure_not_cached(monkeypatch):
    """Si SecureClient.create lanza, la caché NO se populiza y el siguiente intento reintenta."""
    attempt = {"count": 0}

    class FailThenSucceedClient:
        @classmethod
        def create(cls, **kwargs):
            attempt["count"] += 1
            if attempt["count"] == 1:
                raise RuntimeError("auth failed")
            return object()

    fake_mod = types.ModuleType("polymarket")
    fake_mod.SecureClient = FailThenSucceedClient
    monkeypatch.setitem(sys.modules, "polymarket", fake_mod)

    with pytest.raises(RuntimeError):
        build_secure_client(private_key="0xabc")

    # Segundo intento NO debe usar caché (debe reintentar)
    c = build_secure_client(private_key="0xabc")
    assert c is not None
    assert attempt["count"] == 2


# ── tests PublicClient cache ──────────────────────────────────────────────────


def test_public_client_cached(monkeypatch):
    """Dos llamadas a build_public_client devuelven la MISMA instancia."""
    calls: list = []
    _inject_fake_public_client(monkeypatch, calls)

    p1 = build_public_client()
    p2 = build_public_client()

    assert p1 is p2, "Segunda llamada debe devolver el singleton cacheado"
    assert len(calls) == 1, "PublicClient.__init__ solo debe llamarse UNA vez"


def test_public_client_reset_allows_new_instance(monkeypatch):
    """Después de reset_client_cache(), build_public_client construye uno nuevo."""
    calls: list = []
    _inject_fake_public_client(monkeypatch, calls)

    p1 = build_public_client()
    reset_client_cache()
    p2 = build_public_client()

    assert p1 is not p2
    assert len(calls) == 2


# ── test reset_client_cache ───────────────────────────────────────────────────


def test_reset_clears_secure_cache(monkeypatch):
    """reset_client_cache vacía _SECURE_CACHE: el siguiente build llama create de nuevo."""
    calls: list = []
    _inject_fake_polymarket(monkeypatch, calls)

    c1 = build_secure_client(private_key="0xabc")
    reset_client_cache()
    c2 = build_secure_client(private_key="0xabc")

    assert c1 is not c2
    assert len(calls) == 2
