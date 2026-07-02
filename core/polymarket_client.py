"""Fábrica única del cliente autenticado del SDK V2 de Polymarket.

Centraliza la construcción de `SecureClient` (antes duplicada en el broker, el
account_source y varios scripts). Lee la private key / funder de los argumentos o
del entorno, normaliza el prefijo `0x`, y construye el cliente.

Lanza `PolymarketClientError` si falta la key o el SDK no está instalado. Deja
propagar los errores de autenticación de `create()` (red/key inválida) para que
cada caller decida cómo reportarlos (el broker los captura; el account_source los
envuelve en AccountUnavailableError).
"""
from __future__ import annotations

import os

from core.exceptions import PolymarketClientError


def build_secure_client(*, private_key: str | None = None, funder: str | None = None):
    """Construye el `SecureClient` V2 (autenticado, colateral pUSD, wallet derivado)."""
    key = private_key if private_key is not None else (os.getenv("POLYMARKET_PRIVATE_KEY") or "")
    if not key:
        raise PolymarketClientError(
            "Falta POLYMARKET_PRIVATE_KEY para conectar la wallet live."
        )
    if not key.startswith("0x"):
        key = "0x" + key
    try:
        from polymarket import SecureClient
    except ImportError as exc:
        raise PolymarketClientError(
            'SDK live no instalado. Corre: pip install --pre -e ".[live]"'
        ) from exc
    wallet = funder if funder is not None else (os.getenv("POLYMARKET_FUNDER") or None)
    kwargs = {"private_key": key}
    if wallet:
        kwargs["wallet"] = wallet
    return SecureClient.create(**kwargs)
