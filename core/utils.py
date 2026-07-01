"""Utilidades puras compartidas: idempotencia, dinero, tiempo, redacción.

Todo lo de aquí es función pura y testeable en aislamiento.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# ── Tiempo ───────────────────────────────────────────────────────────────────


def utcnow() -> datetime:
    """Ahora en UTC, timezone-aware. Punto único de obtención de tiempo."""
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """Normaliza un datetime a UTC aware (asume UTC si es naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def hours_between(start: datetime, end: datetime) -> float:
    """Horas (float) entre dos instantes. Positivo si end > start."""
    delta = to_utc(end) - to_utc(start)
    return delta.total_seconds() / 3600.0


# ── Dinero / Decimales ───────────────────────────────────────────────────────

_USDC_QUANT = Decimal("0.01")


def to_decimal(value: Any) -> Decimal:
    """Convierte de forma segura a Decimal (vía str para evitar ruido binario)."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def quantize_usdc(value: Any) -> Decimal:
    """Redondea a centavos de USDC (2 decimales, half-up)."""
    return to_decimal(value).quantize(_USDC_QUANT, rounding=ROUND_HALF_UP)


def clamp(value: Decimal, low: Decimal, high: Decimal) -> Decimal:
    """Acota value al rango [low, high]."""
    return max(low, min(high, value))


# ── Idempotencia ─────────────────────────────────────────────────────────────


def make_idempotency_key(
    condition_id: str,
    outcome: str,
    strategy_id: str,
    strategy_version: str,
    date: str,
) -> str:
    """Clave de idempotencia determinística.

    Principio anti-deuda: hash(condition_id + outcome + strategy_id +
    strategy_version + date). Si la key ya existe en AgentDecisionLog, el
    workflow para silenciosamente.

    `date` es una fecha YYYY-MM-DD (no timestamp) para que dos corridas del
    mismo día sobre el mismo mercado/estrategia colisionen como debe ser.
    """
    raw = "|".join([condition_id, outcome, strategy_id, strategy_version, date])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def date_str(dt: datetime | None = None) -> str:
    """Fecha UTC en formato YYYY-MM-DD (para la idempotency_key)."""
    return (to_utc(dt) if dt else utcnow()).strftime("%Y-%m-%d")


# ── Redacción de secretos (para reportes de Editorial) ───────────────────────


def redact_wallet(address: str) -> str:
    """Enmascara una wallet: 0x1234...abcd. Nunca exponer la dirección completa."""
    if not address or len(address) < 10:
        return "0x????"
    return f"{address[:6]}...{address[-4:]}"
