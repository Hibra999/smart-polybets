from __future__ import annotations

from signals.base import SignalProvider

_registry: dict[str, SignalProvider] = {}


def register(provider: SignalProvider) -> None:
    _registry[provider.sport] = provider


def get(sport: str) -> SignalProvider | None:
    return _registry.get(sport)


def clear() -> None:
    _registry.clear()
