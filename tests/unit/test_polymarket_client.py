import pytest

from core.exceptions import PolymarketClientError
from core.polymarket_client import build_secure_client


def test_raises_without_key_explicit():
    # private_key="" (vacío explícito) → error de cliente, sin tocar el SDK ni la red.
    with pytest.raises(PolymarketClientError):
        build_secure_client(private_key="")


def test_raises_without_key_from_env(monkeypatch):
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
    with pytest.raises(PolymarketClientError):
        build_secure_client()


def test_legacy_relayer_key_is_not_used_as_signer(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "01967c03-b8c8-7000-8f68-8b8eaec6fd3d")
    monkeypatch.setenv(
        "RELAYER_API_KEY_ADDRESS", "0x30a886Ac66Ba6ad8cc61Db95ae72f63091Bb4e9b"
    )
    monkeypatch.delenv("RELAYER_API_KEY", raising=False)

    with pytest.raises(PolymarketClientError, match="relayer API key no la sustituye"):
        build_secure_client()


def test_relayer_key_and_address_are_required_as_pair(monkeypatch):
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "a" * 64)
    monkeypatch.setenv("RELAYER_API_KEY", "relayer-key")
    monkeypatch.delenv("RELAYER_API_KEY_ADDRESS", raising=False)

    with pytest.raises(PolymarketClientError, match="deben configurarse juntas"):
        build_secure_client()
