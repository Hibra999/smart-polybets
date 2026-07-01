import pytest

from core.exceptions import AccountUnavailableError
from portfolio.functions.account_source import PolymarketAccountSource


def test_adapter_raises_when_sdk_absent():
    # Con una key presente pero el SDK live no instalado (estado actual del entorno),
    # cualquier lectura debe fallar con AccountUnavailableError (mensaje accionable).
    src = PolymarketAccountSource(private_key="0xdeadbeef")
    with pytest.raises(AccountUnavailableError):
        src.get_balance()


def test_adapter_raises_when_key_missing(monkeypatch):
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
    src = PolymarketAccountSource(private_key=None)
    with pytest.raises(AccountUnavailableError):
        src.get_positions()
