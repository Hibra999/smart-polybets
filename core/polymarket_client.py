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

from core.exceptions import PolymarketClientError

# ── Caché por proceso ────────────────────────────────────────────────────────
_SECURE_CACHE: dict = {}
_PUBLIC_CLIENT = None


def build_secure_client(*, private_key: str | None = None, funder: str | None = None):
    """Construye (o devuelve el cacheado) `SecureClient` V2 (autenticado, pUSD).

    La clave de caché es (private_key_normalizada, funder). Las excepciones NO se
    cachean: un fallo de importación o de red no bloquea reintentos futuros.
    """
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

    cache_key = (key, wallet)
    if cache_key in _SECURE_CACHE:
        return _SECURE_CACHE[cache_key]

    kwargs = {"private_key": key}
    if wallet:
        kwargs["wallet"] = wallet
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
