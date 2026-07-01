"""core/ — utilidades compartidas, sin lógica de negocio.

Ninguna área importa de otra área; sólo de `core/`.
"""
from core.exceptions import (
    AgentError,
    AdapterError,
    DjangoAPIError,
    IdempotencyConflict,
    InsufficientLiquidityError,
    NoActiveStrategyError,
    NotFoundError,
    PriceMovedError,
    SchemaContractError,
    StrategyParseError,
)
from core.types import (
    ModelConfidence,
    OrderSide,
    OrderType,
    SportType,
    VerdictType,
)

__all__ = [
    "AgentError",
    "AdapterError",
    "DjangoAPIError",
    "IdempotencyConflict",
    "InsufficientLiquidityError",
    "NoActiveStrategyError",
    "NotFoundError",
    "PriceMovedError",
    "SchemaContractError",
    "StrategyParseError",
    "ModelConfidence",
    "OrderSide",
    "OrderType",
    "SportType",
    "VerdictType",
]
