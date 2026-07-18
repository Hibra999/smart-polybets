"""Registro de evolución de estrategias: parseo puro de STRATEGY.md/EVOLUTION.md +
validación de drift. Ver docs/superpowers/specs/2026-07-18-strategy-evolution-log-design.md."""
from __future__ import annotations

import re
from pathlib import Path

from core.schemas.strategy_evolution import StrategyEvolutionCheck

REPO = Path(__file__).resolve().parent.parent


def read_strategy_header(strategy_md: str) -> tuple[str | None, str | None]:
    """(version, status) desde las líneas `clave: valor` del HEADER. None si faltan."""
    version = status = None
    for line in strategy_md.splitlines():
        if version is None:
            m = re.match(r"\s*version:\s*([^\s#]+)", line)
            if m:
                version = m.group(1)
        if status is None:
            m = re.match(r"\s*status:\s*([^\s#]+)", line)
            if m:
                status = m.group(1)
    return version, status


def latest_formal_version(evolution_md: str) -> str | None:
    """Versión resultante de la última entrada [FORMAL] (por fecha máxima). None si no hay."""
    best_date: str | None = None
    best_ver: str | None = None
    for line in evolution_md.splitlines():
        s = line.lstrip()
        if not (s.startswith("###") and "[FORMAL]" in s):
            continue
        dm = re.search(r"(\d{4}-\d{2}-\d{2})", s)
        vers = re.findall(r"v(\d+\.\d+)", s)
        if not dm or not vers:
            continue
        d = dm.group(1)
        if best_date is None or d >= best_date:
            best_date, best_ver = d, vers[-1]
    return best_ver
