"""Excepciones del sistema.

Regla de oro del whitepaper: el sistema falla *ruidosamente* antes de operar con
estado inconsistente. Nada de fallos silenciosos.
"""
from __future__ import annotations


class AgentError(Exception):
    """Base de todas las excepciones del sistema."""


class NotFoundError(AgentError):
    """Un recurso esperado no existe (404 del Django App, fila inexistente, etc.)."""


class NoActiveStrategyError(AgentError):
    """No hay una STRATEGY.md aprobada para el torneo solicitado."""


class StrategyParseError(AgentError):
    """Un STRATEGY.md no cumple el formato canónico parseable."""


class SchemaContractError(AgentError):
    """Un dato no cumple el contrato Pydantic esperado entre áreas."""


class AdapterError(AgentError):
    """Fallo en la capa de adapters (lectura de SQLite / modelos)."""


class DjangoAPIError(AgentError):
    """El Django App respondió un error o está caído. El workflow PARA."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class IdempotencyConflict(AgentError):
    """Ya existe un DecisionLog para esta idempotency_key en estado != expired."""


class InsufficientLiquidityError(AgentError):
    """El mercado no tiene volumen/liquidez suficiente para operar."""


class PriceMovedError(AgentError):
    """El precio live se movió más allá de la tolerancia respecto a la señal."""
