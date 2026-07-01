"""Utilidades de consola. Sin lógica de negocio.

`enable_utf8()` fuerza stdout/stderr a UTF-8 para que las tablas y símbolos
(`└`, `·`, `⚠️`, `€`…) no revienten en la consola por defecto de Windows
(cp1252), que lanza `UnicodeEncodeError`. Idempotente y seguro si el stream
no soporta `reconfigure` (p. ej. redirigido a un objeto sin ese método).
"""
from __future__ import annotations

import sys


def enable_utf8() -> None:
    """Reconfigura stdout/stderr a UTF-8 (no-op si no aplica)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass
