"""Carga de `.env` sin dependencias. Sin lógica de negocio.

`load_env()` puebla `os.environ` desde un archivo `.env` (formato `CLAVE=valor`,
comillas opcionales, `#` comenta). NO pisa variables ya definidas en el entorno,
así que un export real siempre gana sobre el archivo.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str | Path = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
