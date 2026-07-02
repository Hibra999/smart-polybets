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


class IdempotencyConflict(AgentError):
    """Ya existe un DecisionLog para esta idempotency_key en estado != expired."""


class InsufficientLiquidityError(AgentError):
    """El mercado no tiene volumen/liquidez suficiente para operar."""


class PriceMovedError(AgentError):
    """El precio live se movió más allá de la tolerancia respecto a la señal."""


class AccountUnavailableError(RuntimeError):
    """La cuenta live de Polymarket no está disponible (SDK no instalado o falta key)."""


class PolymarketClientError(RuntimeError):
    """No se pudo construir el cliente del SDK V2 (falta key o SDK no instalado)."""
