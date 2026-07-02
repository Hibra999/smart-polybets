"""Zonas horarias para PRESENTACIÓN. El almacenamiento es siempre UTC (fuente de
verdad única); esto solo convierte para mostrar al humano.

Contexto:
  - Polymarket etiqueta sus mercados en ET / US Eastern (America/New_York, con DST):
    el título "Will X win on YYYY-MM-DD?" usa la FECHA de ET, no la de UTC.
  - El usuario está en Playa del Carmen (America/Cancun = UTC-5 FIJO, sin DST).

En verano (Mundial) PDC (UTC-5) va 1 hora detrás de ET (EDT, UTC-4), por lo que la
fecha del título de Poly puede ir 1 día adelante de la fecha local. Por eso mostramos
local + ET juntas.

Config por entorno: LOCAL_TZ (default America/Cancun), LOCAL_LABEL (default PDC).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

LOCAL_TZ_NAME = os.getenv("LOCAL_TZ", "America/Cancun")
LOCAL_LABEL = os.getenv("LOCAL_LABEL", "PDC")
ET_TZ = ZoneInfo("America/New_York")


def _resolve(name: str):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return timezone(timedelta(hours=-5))  # fallback: UTC-5 fijo (= Cancún)


LOCAL_TZ = _resolve(LOCAL_TZ_NAME)


def as_utc(dt) -> datetime:
    """Normaliza a datetime UTC tz-aware desde datetime/ISO-str (naive = se asume UTC)."""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_local(dt) -> datetime:
    """UTC -> hora local del usuario (PDC / UTC-5)."""
    return as_utc(dt).astimezone(LOCAL_TZ)


def to_et(dt) -> datetime:
    """UTC -> ET (la zona que Polymarket usa para etiquetar sus mercados)."""
    return as_utc(dt).astimezone(ET_TZ)


def fmt_local_et(dt, *, with_date: bool = True) -> str:
    """'2026-06-30 14:00 PDC / 15:00 ET'. Si la fecha ET difiere de la local, la
    muestra explícita en el lado ET para que cruce con los títulos de Polymarket."""
    if dt is None:
        return "—"
    loc, et = to_local(dt), to_et(dt)
    if not with_date:
        return f"{loc.strftime('%H:%M')} {LOCAL_LABEL} / {et.strftime('%H:%M')} ET"
    left = f"{loc.strftime('%Y-%m-%d %H:%M')} {LOCAL_LABEL}"
    right = (et.strftime('%H:%M') if et.date() == loc.date()
             else et.strftime('%m-%d %H:%M')) + " ET"
    return f"{left} / {right}"


def fmt_local_et_short(dt) -> str:
    """Compacto para columnas de tabla: 'MM-DD HH:MM/HH:MM' (hora local / hora ET)."""
    if dt is None:
        return "—"
    return f"{to_local(dt).strftime('%m-%d %H:%M')}/{to_et(dt).strftime('%H:%M')}"
