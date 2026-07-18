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


def strategy_dirs() -> list[Path]:
    """Carpetas con STRATEGY.md bajo tournaments/*/strategies/*/."""
    return sorted(p.parent for p in REPO.glob("tournaments/*/strategies/*/STRATEGY.md"))


def check_strategy(strategy_dir: Path) -> StrategyEvolutionCheck:
    """Valida que STRATEGY.md v== última [FORMAL] en EVOLUTION.md. Retorna StrategyEvolutionCheck."""
    sid = strategy_dir.name
    version, _status = read_strategy_header(
        (strategy_dir / "STRATEGY.md").read_text(encoding="utf-8"))
    evo = strategy_dir / "EVOLUTION.md"
    if not evo.exists():
        return StrategyEvolutionCheck(
            strategy_id=sid, ok=False, detail="falta EVOLUTION.md",
            remedy_cmd="crear EVOLUTION.md (ver tournaments/STRATEGY_EVOLUTION.md)")
    formal = latest_formal_version(evo.read_text(encoding="utf-8"))
    if formal is None:
        return StrategyEvolutionCheck(
            strategy_id=sid, ok=False, detail="EVOLUTION.md sin entrada [FORMAL]",
            remedy_cmd="agregar la entrada FORMAL de génesis")
    if formal != version:
        return StrategyEvolutionCheck(
            strategy_id=sid, ok=False,
            detail=f"drift: STRATEGY.md v{version} vs última FORMAL v{formal}",
            remedy_cmd="agregar una entrada [FORMAL] que registre el cambio de versión")
    return StrategyEvolutionCheck(strategy_id=sid, ok=True, detail=f"v{version} al día")


def evaluate_all() -> list[StrategyEvolutionCheck]:
    """Valida todas las estrategias. Retorna lista de StrategyEvolutionCheck."""
    return [check_strategy(d) for d in strategy_dirs()]
