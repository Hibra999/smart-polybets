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
