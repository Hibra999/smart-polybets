"""Tools de sincronización con el Django App (WRITE/READ de estado)."""
from __future__ import annotations

from core.django_client import DjangoClient


def _client(client: DjangoClient | None) -> DjangoClient:
    return client or DjangoClient()


def get_active_tournaments(client: DjangoClient | None = None) -> list[dict]:
    return _client(client).get_active_tournaments()


def register_tournament(config: dict, client: DjangoClient | None = None) -> dict:
    return _client(client).register_tournament(config)


def mark_approved(key: str, approved_by: str = "human", client: DjangoClient | None = None) -> dict:
    return _client(client).mark_approved(key, approved_by)


def mark_rejected(key: str, reason: str, client: DjangoClient | None = None) -> dict:
    return _client(client).mark_rejected(key, reason)


def trigger_wallet_sync(client: DjangoClient | None = None) -> dict:
    return _client(client).trigger_wallet_sync()
