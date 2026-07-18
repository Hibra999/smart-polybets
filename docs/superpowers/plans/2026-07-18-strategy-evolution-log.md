# Registro de evolución de estrategias — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estandarizar la evolución de estrategias con un `EVOLUTION.md` append-only por estrategia, una guía global del proceso, y un validador CLI que detecta drift entre `STRATEGY.md` y su última entrada FORMAL.

**Architecture:** Un módulo puro (`core/strategy_evolution.py`) parsea el HEADER del `STRATEGY.md` (version/status vía regex, sin el loader completo — así cubre las estrategias doc-only) y la última entrada FORMAL del `EVOLUTION.md`, y compara. De él cuelgan un CLI advisory (estilo `check_freshness`) y los archivos `EVOLUTION.md` sembrados.

**Tech Stack:** Python 3.13, Pydantic (frozen), pytest, Markdown.

## Global Constraints

- Parsers **puros** sobre texto (sin red, sin el loader `parse_strategy_md` — así funcionan también con estrategias doc-only como `theta_lay_v1`).
- El validador es **advisory** (exit code para vos/CI), nunca bloquea runtime.
- Entradas FORMAL: la cabecera termina con la versión RESULTANTE; el validador toma el **último token `vX.Y`** de la cabecera FORMAL con **fecha máxima** (orden-independiente).
- `EVOLUTION.md` es append-only; solo el bloque "Estado actual" se reescribe.
- 6 estrategias tienen `STRATEGY.md` bajo `tournaments/*/strategies/*/`.
- Todo hallazgo/decisión se documenta en el repo (nunca wiki externa).

---

### Task 1: Schema + parsers puros (`read_strategy_header`, `latest_formal_version`)

**Files:**
- Create: `core/schemas/strategy_evolution.py`
- Create: `core/strategy_evolution.py`
- Test: `tests/unit/test_strategy_evolution_parsers.py`

**Interfaces:**
- Produces:
  - `StrategyEvolutionCheck(strategy_id: str, ok: bool, detail: str = "", remedy_cmd: str | None = None)` — frozen.
  - `read_strategy_header(strategy_md: str) -> tuple[str | None, str | None]` → (version, status).
  - `latest_formal_version(evolution_md: str) -> str | None` → versión de la última entrada FORMAL (fecha máxima).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_strategy_evolution_parsers.py
from core.strategy_evolution import read_strategy_header, latest_formal_version
from core.schemas.strategy_evolution import StrategyEvolutionCheck


def test_read_header():
    md = "# S\n\n## HEADER\nversion: 0.2\nstatus: draft  # comentario\nauthor: X\n"
    assert read_strategy_header(md) == ("0.2", "draft")


def test_read_header_missing():
    assert read_strategy_header("# S\nsin header\n") == (None, None)


def test_latest_formal_picks_max_date():
    evo = (
        "# EVOLUTION\n\n"
        "### 2026-07-14 · v0.1 (génesis) · [FORMAL]\n- x\n\n"
        "### 2026-07-18 · v0.1→v0.2 · [FORMAL]\n- y\n\n"
        "### 2026-07-16 · [OBSERVACIÓN]\n- z\n"
    )
    assert latest_formal_version(evo) == "0.2"


def test_latest_formal_none_when_no_formal():
    assert latest_formal_version("### 2026-07-18 · [OBSERVACIÓN]\n- z\n") is None


def test_check_schema_frozen():
    import pytest
    c = StrategyEvolutionCheck(strategy_id="s", ok=True)
    with pytest.raises(Exception):
        c.ok = False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_strategy_evolution_parsers.py -q`
Expected: FAIL (`ModuleNotFoundError: core.strategy_evolution`).

- [ ] **Step 3: Write minimal implementation**

```python
# core/schemas/strategy_evolution.py
"""Resultado del validador de evolución de estrategias. Frozen."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrategyEvolutionCheck(BaseModel):
    model_config = ConfigDict(frozen=True)

    strategy_id: str
    ok: bool
    detail: str = ""
    remedy_cmd: str | None = None
```

```python
# core/strategy_evolution.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_strategy_evolution_parsers.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add core/schemas/strategy_evolution.py core/strategy_evolution.py tests/unit/test_strategy_evolution_parsers.py
git commit -m "feat: parsers puros de evolución de estrategias (header + última FORMAL)"
```

---

### Task 2: `check_strategy` + `strategy_dirs` + `evaluate_all`

**Files:**
- Modify: `core/strategy_evolution.py`
- Test: `tests/unit/test_strategy_evolution_check.py`

**Interfaces:**
- Consumes: `read_strategy_header`, `latest_formal_version`, `StrategyEvolutionCheck` (Task 1).
- Produces:
  - `strategy_dirs() -> list[Path]` — carpetas con `STRATEGY.md` bajo `tournaments/*/strategies/*/`.
  - `check_strategy(strategy_dir: Path) -> StrategyEvolutionCheck`.
  - `evaluate_all() -> list[StrategyEvolutionCheck]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_strategy_evolution_check.py
from pathlib import Path

import core.strategy_evolution as se


def _mk(dirp: Path, strat: str, evo: str | None):
    dirp.mkdir(parents=True, exist_ok=True)
    (dirp / "STRATEGY.md").write_text(strat, encoding="utf-8")
    if evo is not None:
        (dirp / "EVOLUTION.md").write_text(evo, encoding="utf-8")


def test_ok_when_versions_match(tmp_path):
    d = tmp_path / "s"
    _mk(d, "## HEADER\nversion: 0.2\nstatus: draft\n",
        "### 2026-07-18 · v0.1→v0.2 · [FORMAL]\n- x\n")
    r = se.check_strategy(d)
    assert r.ok is True


def test_drift_when_versions_differ(tmp_path):
    d = tmp_path / "s"
    _mk(d, "## HEADER\nversion: 0.2\nstatus: draft\n",
        "### 2026-07-14 · v0.1 (génesis) · [FORMAL]\n- x\n")
    r = se.check_strategy(d)
    assert r.ok is False and "drift" in r.detail.lower()


def test_missing_evolution(tmp_path):
    d = tmp_path / "s"
    _mk(d, "## HEADER\nversion: 0.1\nstatus: draft\n", None)
    r = se.check_strategy(d)
    assert r.ok is False and "EVOLUTION" in r.detail


def test_no_formal_entry(tmp_path):
    d = tmp_path / "s"
    _mk(d, "## HEADER\nversion: 0.1\nstatus: draft\n",
        "### 2026-07-18 · [OBSERVACIÓN]\n- z\n")
    r = se.check_strategy(d)
    assert r.ok is False and "FORMAL" in r.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_strategy_evolution_check.py -q`
Expected: FAIL (`AttributeError: ... 'check_strategy'`).

- [ ] **Step 3: Write minimal implementation** (append to `core/strategy_evolution.py`)

```python
def strategy_dirs() -> list[Path]:
    return sorted(p.parent for p in REPO.glob("tournaments/*/strategies/*/STRATEGY.md"))


def check_strategy(strategy_dir: Path) -> StrategyEvolutionCheck:
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
    return [check_strategy(d) for d in strategy_dirs()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_strategy_evolution_check.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add core/strategy_evolution.py tests/unit/test_strategy_evolution_check.py
git commit -m "feat: validación de drift STRATEGY.md vs EVOLUTION.md (check_strategy/evaluate_all)"
```

---

### Task 3: CLI `scripts/check_strategy_evolution.py`

**Files:**
- Create: `scripts/check_strategy_evolution.py`
- Test: `tests/unit/test_check_strategy_evolution_cli.py`

**Interfaces:**
- Consumes: `core.strategy_evolution.evaluate_all`.
- Produces: `run(as_json: bool = False) -> int` (0 sin drift, 2 con drift); `main()` → `sys.exit(run(...))`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_check_strategy_evolution_cli.py
import importlib

from core.schemas.strategy_evolution import StrategyEvolutionCheck


def _load(monkeypatch, results):
    mod = importlib.import_module("scripts.check_strategy_evolution")
    monkeypatch.setattr(mod.se, "evaluate_all", lambda: results)
    return mod


def test_exit_zero_all_ok(monkeypatch):
    mod = _load(monkeypatch, [StrategyEvolutionCheck(strategy_id="s", ok=True)])
    assert mod.run(as_json=False) == 0


def test_exit_two_on_drift(monkeypatch):
    mod = _load(monkeypatch, [StrategyEvolutionCheck(strategy_id="s", ok=False, detail="drift")])
    assert mod.run(as_json=False) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_check_strategy_evolution_cli.py -q`
Expected: FAIL (`ModuleNotFoundError: scripts.check_strategy_evolution`).

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python
"""check_strategy_evolution.py — verifica que cada STRATEGY.md tenga su EVOLUTION.md al
día (la última entrada [FORMAL] declara la misma version). Advisory: exit 2 si hay drift.

    python scripts/check_strategy_evolution.py
    python scripts/check_strategy_evolution.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8  # noqa: E402

enable_utf8()

import core.strategy_evolution as se  # noqa: E402


def run(as_json: bool = False) -> int:
    results = se.evaluate_all()
    drift = [r for r in results if not r.ok]
    if as_json:
        print(json.dumps({"ok": not drift,
                          "results": [r.model_dump(mode="json") for r in results]},
                         indent=2, default=str))
    else:
        print("\n=== Evolución de estrategias ===")
        for r in results:
            print(f"  {'OK ' if r.ok else '!! '}{r.strategy_id}: {r.detail}")
            if not r.ok and r.remedy_cmd:
                print(f"        → {r.remedy_cmd}")
        print(f"\n  {'TODO AL DÍA' if not drift else 'HAY DRIFT — registrá la evolución'}\n")
    return 0 if not drift else 2


def main() -> None:
    ap = argparse.ArgumentParser(description="Validador de evolución de estrategias.")
    ap.add_argument("--json", action="store_true")
    sys.exit(run(ap.parse_args().json))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_check_strategy_evolution_cli.py -q`
Expected: PASS (2 tests). Luego correr el CLI real (aún reportará drift/faltantes hasta el bootstrap de Task 5): `python scripts/check_strategy_evolution.py; echo "exit=$?"`.

- [ ] **Step 5: Commit**

```bash
git add scripts/check_strategy_evolution.py tests/unit/test_check_strategy_evolution_cli.py
git commit -m "feat: CLI check_strategy_evolution (drift STRATEGY.md vs EVOLUTION.md)"
```

---

### Task 4: La guía `tournaments/STRATEGY_EVOLUTION.md` + regla de oro

**Files:**
- Create: `tournaments/STRATEGY_EVOLUTION.md`
- Modify: `CLAUDE.md` (sección "Reglas de oro")

**Interfaces:** ninguna (documentación).

- [ ] **Step 1: Crear la guía** con este contenido:

```markdown
# Guía — Evolución de estrategias

Cada estrategia lleva un `EVOLUTION.md` append-only junto a su `STRATEGY.md`. Registra
su evolución para **auditar** (por qué estaba en el estado X en la versión N) y
**aprender** (qué se probó/descartó, qué sigue).

## Cuándo se registra
- **FORMAL** — en TODO cambio de `version` o `status` del `STRATEGY.md`. Atada a un
  diff del config + evidencia + nota de reproducibilidad.
- **OBSERVACIÓN** — cuando se prueba, descarta o pausa una idea SIN cambiar el config
  (hipótesis→prueba→resultado→disposición).

## Regla: cambio de config → bump de version
Cualquier cambio a los params/thresholds del `STRATEGY.md` **bumpea la `version`** y
lleva su entrada FORMAL. Esto NO es cosmético: la `version` es `strategy_version`, que
entra en la idempotency key (regla de oro #4) — si las reglas cambian pero la version no,
dos decisiones distintas comparten key. El validador (abajo) hace cumplir que la version
y la última FORMAL coincidan.

## Ciclo de vida y evidencia por transición
- `draft → under_review`: ≥1 OBSERVACIÓN con resultado + una hipótesis de edge.
- `under_review → approved`: entrada FORMAL que cite un **backtest con edge** (o
  evidencia live equivalente) + sizing definido.
- `* → deprecated`: entrada FORMAL con la razón del retiro.

## Formato (ver `EVOLUTION.md` de cualquier estrategia)
- Arriba, un bloque **Estado actual** (version · status · postura · preguntas abiertas ·
  próximo paso) — se reescribe cada sesión que toca la estrategia.
- Debajo, entradas reverse-cronológicas. Cabecera FORMAL: `### YYYY-MM-DD · vX→vY ·
  [FORMAL]` (o `vX (génesis)`); cabecera observación: `### YYYY-MM-DD · [OBSERVACIÓN]`.

## Validación
`python scripts/check_strategy_evolution.py` verifica que la última entrada FORMAL
declare la misma `version` que el `STRATEGY.md` (drift → exit 2). Advisory.

## Estrategias doc-only
Las que no se cargan por el pipeline (`theta_lay_v1`, marcada "Doc-only") igual llevan
`EVOLUTION.md`; el validador no compara contra el loader pero sí exige el ledger.
```

- [ ] **Step 2: Regla de oro en CLAUDE.md.** En la sección "## Reglas de oro (anti-deuda técnica)", agregar un ítem nuevo al final de la lista numerada:

```markdown
9. **Toda evolución de una estrategia se registra en su `EVOLUTION.md`**: cambios de
   params/status (entrada FORMAL con evidencia) o ideas probadas/descartadas
   (OBSERVACIÓN). Guía y ciclo de vida en `tournaments/STRATEGY_EVOLUTION.md`; drift lo
   marca `scripts/check_strategy_evolution.py`.
```

- [ ] **Step 3: Verificar**

Run: `python -c "import ast" ` (no aplica) — en su lugar: `test -f tournaments/STRATEGY_EVOLUTION.md && grep -q "EVOLUTION.md" CLAUDE.md && echo OK`.
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add tournaments/STRATEGY_EVOLUTION.md CLAUDE.md
git commit -m "docs: guía de evolución de estrategias + regla de oro"
```

---

### Task 5: Bootstrap de los `EVOLUTION.md` + verificación end-to-end

**Files:**
- Create: `tournaments/fifa_world_cup_2026/strategies/match_winner_wc_v1/EVOLUTION.md`
- Create: `tournaments/fifa_world_cup_2026/strategies/match_winner_v1/EVOLUTION.md`
- Create: `tournaments/fifa_world_cup_2026/strategies/top_scorer_v1/EVOLUTION.md`
- Create: `tournaments/liga_mx_2026/strategies/match_winner_ligamx_v1/EVOLUTION.md`
- Create: `tournaments/liga_mx_2026/strategies/theta_lay_v1/EVOLUTION.md`
- Create: `tournaments/nfl_2026/strategies/game_winner_v1/EVOLUTION.md`

**Interfaces:** consume el validador de Task 3 para verificar (todas las estrategias `ok`).

- [ ] **Step 1: Leer el estado real de cada estrategia** para sembrar con datos ciertos (no inventar):
  - `git log --oneline --follow -- <cada STRATEGY.md>` para hitos.
  - El `version`/`status` actual de cada `STRATEGY.md` (la génesis FORMAL DEBE declarar esa misma versión, o el validador marcará drift).
  - Findings citados (WC: migración + `2026-07-13-poisson-sesgo-knockout.md`; Liga MX: `2026-07-14-ligamx-backtest.md`).

- [ ] **Step 2: Sembrar cada `EVOLUTION.md`** siguiendo el formato de la guía. Reglas:
  - La **última entrada FORMAL** de cada archivo debe declarar EXACTAMENTE el `version` del `STRATEGY.md` actual (si no, drift). Verificá el version de cada STRATEGY.md antes de escribir.
  - **Bootstrap = la historia previa se absorbe en la génesis** (la regla "cambio de config → bump" aplica de acá para adelante, NO retroactivamente). La génesis FORMAL declara el `version` ACTUAL del `STRATEGY.md` tal cual, y narra en el cuerpo los cambios previos a este registro — así el validador queda verde sin editar ningún `STRATEGY.md`.
  - `match_winner_ligamx_v1` (v0.1): génesis FORMAL `### 2026-07-18 · v0.1 (génesis) · [FORMAL]` que declara v0.1 y menciona en el cuerpo el ajuste de umbral 0.05→0.10 (E3, `docs/findings/2026-07-14-ligamx-backtest.md`); + OBSERVACIÓN "backtest sin edge" (2026-07-14). NO se bumpea a v0.2 (absorción histórica; la estrategia nunca operó, no hay idempotency keys con v0.1).
  - `match_winner_wc_v1` (v1.0): génesis `v1.0` (migración de `pypro_worldcup_betting`) + OBSERVACIÓN del sesgo Poisson en knockout (`docs/findings/2026-07-13-poisson-sesgo-knockout.md`) + OBSERVACIÓN de `bet_type` (double_chance). Última FORMAL debe ser `v1.0`.
  - `theta_lay_v1` (v0.1, doc-only): génesis `v0.1` + OBSERVACIÓN de la evidencia de concepto del WC + la validación J1-J3 pendiente como próximo paso.
  - `game_winner_v1` (NFL): génesis con el `version`/`status` reales de su STRATEGY.md (leer antes).
  - `match_winner_v1` y `top_scorer_v1` (WC legacy): génesis mínima con su version/status real + una nota de que son base/legacy.
  - Cada archivo abre con el bloque **Estado actual**.

- [ ] **Step 3: Verificar end-to-end** — el validador debe quedar verde:

Run: `python scripts/check_strategy_evolution.py; echo "exit=$?"`
Expected: todas las estrategias `OK`, `TODO AL DÍA`, `exit=0`. Si alguna marca drift, corregí la cabecera FORMAL de su `EVOLUTION.md` para que declare el version real del `STRATEGY.md`.

- [ ] **Step 4: Suite completa**

Run: `python -m pytest tests/unit -q`
Expected: verde.

- [ ] **Step 5: Commit**

```bash
git add tournaments/*/strategies/*/EVOLUTION.md
git commit -m "chore: bootstrap EVOLUTION.md de las 6 estrategias (genesis + hitos reales)"
```

---

## Notas de verificación final
- `python scripts/check_strategy_evolution.py` → todas OK, exit 0.
- `python -m pytest tests/unit -q` → verde.
- Un cambio futuro de `version`/`status` en un `STRATEGY.md` sin su entrada FORMAL → el validador marca drift (exit 2).
