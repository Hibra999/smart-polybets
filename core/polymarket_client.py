"""Fábrica única del cliente autenticado del SDK V2 de Polymarket.

Centraliza la construcción de `SecureClient` (antes duplicada en el broker, el
account_source y varios scripts). Lee la private key / funder de los argumentos o
del entorno, normaliza el prefijo `0x`, y construye el cliente.

Lanza `PolymarketClientError` si falta la key o el SDK no está instalado. Deja
propagar los errores de autenticación de `create()` (red/key inválida) para que
cada caller decida cómo reportarlos (el broker los captura; el account_source los
envuelve en AccountUnavailableError).

Caché por proceso: `build_secure_client` y `build_public_client` devuelven la misma
instancia para los mismos parámetros dentro del mismo proceso, evitando re-auth
costosa (~8-12 s) en cada invocación. Llamar `reset_client_cache()` para limpiar
(tests).
"""
from __future__ import annotations

import os
import re

from core.exceptions import PolymarketClientError

# ── Caché por proceso ────────────────────────────────────────────────────────
_SECURE_CACHE: dict = {}
_PUBLIC_CLIENT = None
_EVM_PRIVATE_KEY = re.compile(r"^(?:0x)?[0-9a-fA-F]{64}$")
_RELAYER_API_KEY = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def is_evm_private_key(value: str | None) -> bool:
    """True sólo para una clave EVM de 32 bytes, con prefijo 0x opcional."""
    return bool(value and _EVM_PRIVATE_KEY.fullmatch(value))


def is_relayer_api_key(value: str | None) -> bool:
    """True para el formato UUID emitido actualmente por el relayer."""
    return bool(value and _RELAYER_API_KEY.fullmatch(value))


def build_secure_client(
    *,
    private_key: str | None = None,
    funder: str | None = None,
    relayer_api_key: str | None = None,
    relayer_api_key_address: str | None = None,
):
    """Construye (o devuelve el cacheado) `SecureClient` V2 (autenticado, pUSD).

    La clave de caché incluye signer, wallet y relayer. Las excepciones NO se
    cachean: un fallo de importación o de red no bloquea reintentos futuros.
    """
    env_key = os.getenv("POLYMARKET_PRIVATE_KEY") or ""
    key = private_key if private_key is not None else env_key

    # Compatibilidad local: una UUID guardada antiguamente como PRIVATE_KEY es en
    # realidad una relayer API key. Se aprovecha como tal, pero nunca como signer.
    legacy_relayer_key = ""
    if private_key is None and is_relayer_api_key(key):
        legacy_relayer_key, key = key, ""

    relayer_key = (
        relayer_api_key
        if relayer_api_key is not None
        else (os.getenv("RELAYER_API_KEY") or legacy_relayer_key)
    )
    relayer_address = (
        relayer_api_key_address
        if relayer_api_key_address is not None
        else ((os.getenv("RELAYER_API_KEY_ADDRESS") or "") if relayer_key else "")
    )
    if bool(relayer_key) != bool(relayer_address):
        raise PolymarketClientError(
            "RELAYER_API_KEY y RELAYER_API_KEY_ADDRESS deben configurarse juntas."
        )
    if not key:
        raise PolymarketClientError(
            "Falta una POLYMARKET_PRIVATE_KEY EVM para firmar; la relayer API key no la sustituye."
        )
    if not key.startswith("0x"):
        key = "0x" + key
    try:
        from polymarket import SecureClient
        if relayer_key:
            from polymarket import RelayerApiKey
    except ImportError as exc:
        raise PolymarketClientError(
            'SDK live no instalado. Corre: pip install --pre -e ".[live]"'
        ) from exc
    wallet = funder if funder is not None else (os.getenv("POLYMARKET_FUNDER") or None)

    cache_key = (key, wallet, relayer_key, relayer_address)
    if cache_key in _SECURE_CACHE:
        return _SECURE_CACHE[cache_key]

    kwargs = {"private_key": key}
    if wallet:
        kwargs["wallet"] = wallet
    if relayer_key:
        kwargs["api_key"] = RelayerApiKey(key=relayer_key, address=relayer_address)
    client = SecureClient.create(**kwargs)
    _SECURE_CACHE[cache_key] = client
    return client


def build_public_client():
    """Construye (o devuelve el cacheado) `PublicClient` del SDK (read-only, sin auth).

    Singleton por proceso. Lanza `PolymarketClientError` si el SDK no está instalado.
    """
    global _PUBLIC_CLIENT
    if _PUBLIC_CLIENT is not None:
        return _PUBLIC_CLIENT
    try:
        from polymarket.clients.public import PublicClient
    except ImportError as exc:
        raise PolymarketClientError(
            "SDK polymarket-client no instalado. Instalar: pip install --pre polymarket-client"
        ) from exc
    _PUBLIC_CLIENT = PublicClient()
    return _PUBLIC_CLIENT


def reset_client_cache() -> None:
    """Limpia ambos caches de clientes (para tests)."""
    global _PUBLIC_CLIENT
    _SECURE_CACHE.clear()
    _PUBLIC_CLIENT = None
