# Validaciones mandatorias de dependencias — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforcear las dependencias de frescura de datos ("refrescar antes de sugerir/apostar") con precondiciones puras + guards por nivel de acción + un hook `SessionStart`.

**Architecture:** Un módulo puro (`core/preconditions.py`) es la única fuente de verdad de "qué está fresco": predicados deterministas sobre SQLite read-only + env. Del módulo cuelgan tres capas — guards en las acciones (`enforce()`), un CLI (`check_freshness.py`), y un hook `SessionStart` en `.claude/settings.json`.

**Tech Stack:** Python 3.13, Pydantic (frozen), sqlite3 (stdlib), pytest. Claude Code hooks (settings.json).

## Global Constraints

- Precondiciones = funciones **puras** sobre estado local (SQLite RO + env). Sin red en las mandatory; la advisory degrada a `ok=None` si no puede verificar. Nunca rompen la acción.
- Tiers: `READ` (avisa y sigue) · `MONEY` (hard-block salvo `--force --reason`).
- `live_gates_ready` solo se evalúa cuando la acción va con `--live` (no bloquear dry-runs).
- Alcance por torneo: una acción de dinero sobre un torneo concreto evalúa solo ese torneo; las lecturas transversales evalúan todos los activos.
- DB por torneo: `data/<tid>/<tid>.sqlite`. Torneos activos: `start_date <= hoy <= end_date` en `tournaments.registry.TOURNAMENTS`.
- Tiempo: `core.utils.utcnow()`. Margen para no marcar partidos en juego: `GRACE_MINUTES = 150`.
- Todo hallazgo/decisión se documenta en el repo (nunca wiki externa).

---

### Task 1: Schema `PreconditionResult`

**Files:**
- Create: `core/schemas/precondition.py`
- Test: `tests/unit/test_precondition_schema.py`

**Interfaces:**
- Consumes: nada.
- Produces: `PreconditionResult(name: str, ok: bool | None, severity: Literal["mandatory","advisory"], tournament_id: str | None = None, detail: str = "", remedy_cmd: str | None = None)` — frozen; property `is_violation -> bool` (True sólo si `severity=="mandatory" and ok is False`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_precondition_schema.py
from core.schemas.precondition import PreconditionResult


def test_is_violation_only_for_mandatory_false():
    assert PreconditionResult(name="x", ok=False, severity="mandatory").is_violation is True
    assert PreconditionResult(name="x", ok=False, severity="advisory").is_violation is False
    assert PreconditionResult(name="x", ok=True, severity="mandatory").is_violation is False
    assert PreconditionResult(name="x", ok=None, severity="mandatory").is_violation is False


def test_frozen():
    import pytest
    r = PreconditionResult(name="x", ok=True, severity="mandatory")
    with pytest.raises(Exception):
        r.name = "y"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_precondition_schema.py -q`
Expected: FAIL (`ModuleNotFoundError: core.schemas.precondition`).

- [ ] **Step 3: Write minimal implementation**

```python
# core/schemas/precondition.py
"""Resultado de una precondición de datos. Frozen. Ver
docs/superpowers/specs/2026-07-17-mandatory-dependency-hooks-design.md."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class PreconditionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    ok: bool | None                       # True=cumple, False=viola, None=no verificable
    severity: Literal["mandatory", "advisory"]
    tournament_id: str | None = None
    detail: str = ""
    remedy_cmd: str | None = None

    @property
    def is_violation(self) -> bool:
        return self.severity == "mandatory" and self.ok is False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_precondition_schema.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add core/schemas/precondition.py tests/unit/test_precondition_schema.py
git commit -m "feat: schema PreconditionResult para validaciones de dependencias"
```

---

### Task 2: `fixtures_finalized` + resolución de torneos/DB

**Files:**
- Create: `core/preconditions.py`
- Test: `tests/unit/test_preconditions_fixtures.py`

**Interfaces:**
- Consumes: `PreconditionResult` (Task 1); `core.utils.utcnow`; `tournaments.registry.TOURNAMENTS`.
- Produces:
  - `REPO: Path`, `GRACE_MINUTES = 150`
  - `db_path(tid: str) -> Path` → `REPO/"data"/tid/f"{tid}.sqlite"`
  - `active_tournaments(today: date | None = None) -> list[str]`
  - `check_fixtures_finalized(tid: str, *, now: datetime | None = None) -> PreconditionResult`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_preconditions_fixtures.py
import sqlite3
from datetime import datetime, timedelta, timezone

import core.preconditions as pc


def _mk_db(path, rows):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE team (id TEXT PRIMARY KEY, name TEXT, elo_rating REAL)")
    con.execute("CREATE TABLE fixture (id TEXT, home_team_id TEXT, away_team_id TEXT, "
                "kickoff_utc TEXT, status TEXT)")
    con.execute("INSERT INTO team VALUES ('a','A',1500),('b','B',1500)")
    con.executemany("INSERT INTO fixture VALUES (?,?,?,?,?)", rows)
    con.commit(); con.close()


def test_fixtures_finalized_flags_past_scheduled(tmp_path, monkeypatch):
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    old = (now - timedelta(hours=5)).isoformat()      # jugado, sin finalizar
    con_db = tmp_path / "t.sqlite"
    _mk_db(con_db, [("f1", "a", "b", old, "scheduled")])
    monkeypatch.setattr(pc, "db_path", lambda tid: con_db)
    r = pc.check_fixtures_finalized("liga_mx_2026", now=now)
    assert r.is_violation is True
    assert "update_results.py --tournament liga_mx_2026" in r.remedy_cmd


def test_in_play_not_flagged(tmp_path, monkeypatch):
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(minutes=30)).isoformat()  # en juego ahora
    con_db = tmp_path / "t.sqlite"
    _mk_db(con_db, [("f1", "a", "b", recent, "scheduled")])
    monkeypatch.setattr(pc, "db_path", lambda tid: con_db)
    assert pc.check_fixtures_finalized("liga_mx_2026", now=now).ok is True


def test_missing_db_is_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "db_path", lambda tid: tmp_path / "nope.sqlite")
    r = pc.check_fixtures_finalized("x", now=datetime(2026, 7, 17, tzinfo=timezone.utc))
    assert r.ok is None and r.is_violation is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_preconditions_fixtures.py -q`
Expected: FAIL (`ModuleNotFoundError: core.preconditions`).

- [ ] **Step 3: Write minimal implementation**

```python
# core/preconditions.py
"""Precondiciones de frescura de datos (funciones puras). Única fuente de verdad
de 'qué está fresco'. Ver docs/superpowers/specs/2026-07-17-mandatory-dependency-hooks-design.md."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from core.schemas.precondition import PreconditionResult
from core.utils import utcnow
from tournaments.registry import TOURNAMENTS

REPO = Path(__file__).resolve().parent.parent
GRACE_MINUTES = 150  # margen para no marcar partidos en juego como 'sin finalizar'


def db_path(tid: str) -> Path:
    return REPO / "data" / tid / f"{tid}.sqlite"


def active_tournaments(today: date | None = None) -> list[str]:
    today = today or utcnow().date()
    out = []
    for tid, cfg in TOURNAMENTS.items():
        start = date.fromisoformat(cfg.start_date)
        end = date.fromisoformat(cfg.end_date)
        if start <= today <= end:
            out.append(tid)
    return out


def check_fixtures_finalized(tid: str, *, now: datetime | None = None) -> PreconditionResult:
    now = now or utcnow()
    cutoff = (now - timedelta(minutes=GRACE_MINUTES)).isoformat()
    db = db_path(tid)
    if not db.exists():
        return PreconditionResult(name="fixtures_finalized", ok=None, severity="mandatory",
                                  tournament_id=tid, detail=f"DB no encontrada: {db}")
    con = sqlite3.connect(db)
    try:
        (n,) = con.execute(
            "SELECT COUNT(*) FROM fixture WHERE status='scheduled' AND kickoff_utc < ?",
            (cutoff,)).fetchone()
    except sqlite3.OperationalError as exc:
        return PreconditionResult(name="fixtures_finalized", ok=None, severity="mandatory",
                                  tournament_id=tid, detail=f"no verificable: {exc}")
    finally:
        con.close()
    ok = n == 0
    return PreconditionResult(
        name="fixtures_finalized", ok=ok, severity="mandatory", tournament_id=tid,
        detail=("datos al día" if ok else f"{n} partido(s) jugado(s) sin finalizar"),
        remedy_cmd=None if ok else f"python scripts/update_results.py --tournament {tid} --apply")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_preconditions_fixtures.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add core/preconditions.py tests/unit/test_preconditions_fixtures.py
git commit -m "feat: precondicion fixtures_finalized + resolucion de torneos activos"
```

---

### Task 3: `placeholders_synced` (advisory, local) + `live_gates_ready`

**Files:**
- Modify: `core/preconditions.py` (agrega dos funciones)
- Test: `tests/unit/test_preconditions_extra.py`

**Interfaces:**
- Consumes: `PreconditionResult`, `db_path`, `utcnow`, `os`.
- Produces:
  - `check_placeholders_synced(tid: str, *, now: datetime | None = None, horizon_days: int = 3) -> PreconditionResult` (severity advisory)
  - `check_live_gates_ready() -> PreconditionResult` (severity mandatory; `tournament_id=None`)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_preconditions_extra.py
import sqlite3
from datetime import datetime, timedelta, timezone

import core.preconditions as pc


def _mk_db(path, fixtures, teams):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE team (id TEXT PRIMARY KEY, name TEXT, elo_rating REAL)")
    con.execute("CREATE TABLE fixture (id TEXT, home_team_id TEXT, away_team_id TEXT, "
                "kickoff_utc TEXT, status TEXT)")
    con.executemany("INSERT INTO team VALUES (?,?,?)", teams)
    con.executemany("INSERT INTO fixture VALUES (?,?,?,?,?)", fixtures)
    con.commit(); con.close()


def test_placeholder_upcoming_is_advisory_violation(tmp_path, monkeypatch):
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    soon = (now + timedelta(days=1)).isoformat()
    db = tmp_path / "t.sqlite"
    _mk_db(db, [("f1", "real", "ph", soon, "scheduled")],
           [("real", "Real", 1500.0), ("ph", "Placeholder", None)])
    monkeypatch.setattr(pc, "db_path", lambda tid: db)
    r = pc.check_placeholders_synced("fifa_world_cup_2026", now=now)
    assert r.severity == "advisory" and r.ok is False and r.is_violation is False


def test_no_placeholders_ok(tmp_path, monkeypatch):
    now = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)
    soon = (now + timedelta(days=1)).isoformat()
    db = tmp_path / "t.sqlite"
    _mk_db(db, [("f1", "a", "b", soon, "scheduled")],
           [("a", "A", 1500.0), ("b", "B", 1500.0)])
    monkeypatch.setattr(pc, "db_path", lambda tid: db)
    assert pc.check_placeholders_synced("x", now=now).ok is True


def test_live_gates(monkeypatch):
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
    monkeypatch.setenv("POLYMARKET_LIVE", "0")
    monkeypatch.delenv("POLYMARKET_KILL_SWITCH", raising=False)
    assert pc.check_live_gates_ready().is_violation is True
    monkeypatch.setenv("POLYMARKET_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("POLYMARKET_LIVE", "1")
    assert pc.check_live_gates_ready().ok is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_preconditions_extra.py -q`
Expected: FAIL (`AttributeError: module 'core.preconditions' has no attribute 'check_placeholders_synced'`).

- [ ] **Step 3: Write minimal implementation** (append to `core/preconditions.py`)

```python
import os  # (subir al bloque de imports del módulo)

_TRUTHY = ("1", "true", "yes", "on")


def check_placeholders_synced(tid: str, *, now: datetime | None = None,
                              horizon_days: int = 3) -> PreconditionResult:
    now = now or utcnow()
    lo, hi = now.isoformat(), (now + timedelta(days=horizon_days)).isoformat()
    db = db_path(tid)
    if not db.exists():
        return PreconditionResult(name="placeholders_synced", ok=None, severity="advisory",
                                  tournament_id=tid, detail=f"DB no encontrada: {db}")
    con = sqlite3.connect(db)
    try:
        (n,) = con.execute(
            "SELECT COUNT(*) FROM fixture f "
            "JOIN team h ON h.id=f.home_team_id JOIN team a ON a.id=f.away_team_id "
            "WHERE f.status='scheduled' AND f.kickoff_utc BETWEEN ? AND ? "
            "AND (h.elo_rating IS NULL OR a.elo_rating IS NULL)", (lo, hi)).fetchone()
    except sqlite3.OperationalError as exc:
        return PreconditionResult(name="placeholders_synced", ok=None, severity="advisory",
                                  tournament_id=tid, detail=f"no verificable: {exc}")
    finally:
        con.close()
    ok = n == 0
    return PreconditionResult(
        name="placeholders_synced", ok=ok, severity="advisory", tournament_id=tid,
        detail=("placeholders al día" if ok else f"{n} fixture(s) próximos con equipo placeholder"),
        remedy_cmd=None if ok else "python scripts/sync_upcoming_fixtures.py --apply")


def check_live_gates_ready() -> PreconditionResult:
    problems = []
    if not os.getenv("POLYMARKET_PRIVATE_KEY"):
        problems.append("falta POLYMARKET_PRIVATE_KEY")
    if os.getenv("POLYMARKET_LIVE", "") not in _TRUTHY:
        problems.append("POLYMARKET_LIVE!=1")
    if os.getenv("POLYMARKET_KILL_SWITCH", "") in _TRUTHY:
        problems.append("kill-switch activo")
    ok = not problems
    return PreconditionResult(
        name="live_gates_ready", ok=ok, severity="mandatory", tournament_id=None,
        detail=("gates live OK" if ok else "; ".join(problems)),
        remedy_cmd=None if ok else "setear POLYMARKET_LIVE=1 + key y POLYMARKET_KILL_SWITCH=0")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_preconditions_extra.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add core/preconditions.py tests/unit/test_preconditions_extra.py
git commit -m "feat: precondiciones placeholders_synced (advisory) y live_gates_ready"
```

---

### Task 4: `evaluate()` + `enforce()`

**Files:**
- Modify: `core/preconditions.py`
- Test: `tests/unit/test_preconditions_enforce.py`

**Interfaces:**
- Consumes: las tres funciones `check_*` (Tasks 2-3).
- Produces:
  - `evaluate(tier: str, tournaments: list[str] | None = None, *, now=None, live: bool = False) -> list[PreconditionResult]`
  - `enforce(tier: str, *, tournaments=None, force: bool = False, reason: str | None = None, live: bool = False) -> None` — imprime; en tier `MONEY` con violación y sin `force` hace `raise SystemExit(2)`; `force` sin `reason` también `raise SystemExit(2)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_preconditions_enforce.py
import pytest

import core.preconditions as pc
from core.schemas.precondition import PreconditionResult


def _viol(tid="wc"):
    return PreconditionResult(name="fixtures_finalized", ok=False, severity="mandatory",
                              tournament_id=tid, detail="1 sin finalizar",
                              remedy_cmd="python scripts/update_results.py --tournament wc --apply")


def test_read_warns_and_proceeds(monkeypatch, capsys):
    monkeypatch.setattr(pc, "evaluate", lambda *a, **k: [_viol()])
    pc.enforce("READ")                      # no levanta
    assert "sin finalizar" in capsys.readouterr().out


def test_money_blocks_without_force(monkeypatch):
    monkeypatch.setattr(pc, "evaluate", lambda *a, **k: [_viol()])
    with pytest.raises(SystemExit):
        pc.enforce("MONEY")


def test_money_force_needs_reason(monkeypatch):
    monkeypatch.setattr(pc, "evaluate", lambda *a, **k: [_viol()])
    with pytest.raises(SystemExit):
        pc.enforce("MONEY", force=True)     # sin reason


def test_money_force_with_reason_proceeds(monkeypatch, capsys):
    monkeypatch.setattr(pc, "evaluate", lambda *a, **k: [_viol()])
    pc.enforce("MONEY", force=True, reason="verificado a mano")
    assert "FORZADO" in capsys.readouterr().out


def test_evaluate_includes_gates_only_when_live(monkeypatch):
    monkeypatch.setattr(pc, "check_fixtures_finalized", lambda tid, **k:
                        PreconditionResult(name="fixtures_finalized", ok=True, severity="mandatory"))
    monkeypatch.setattr(pc, "check_placeholders_synced", lambda tid, **k:
                        PreconditionResult(name="placeholders_synced", ok=True, severity="advisory"))
    names_dry = [r.name for r in pc.evaluate("MONEY", tournaments=["wc"], live=False)]
    names_live = [r.name for r in pc.evaluate("MONEY", tournaments=["wc"], live=True)]
    assert "live_gates_ready" not in names_dry
    assert "live_gates_ready" in names_live
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_preconditions_enforce.py -q`
Expected: FAIL (`AttributeError: ... 'evaluate'`).

- [ ] **Step 3: Write minimal implementation** (append to `core/preconditions.py`)

```python
def evaluate(tier: str, tournaments: list[str] | None = None, *, now=None,
             live: bool = False) -> list[PreconditionResult]:
    tids = tournaments if tournaments is not None else active_tournaments(
        None if now is None else now.date())
    results: list[PreconditionResult] = []
    for tid in tids:
        results.append(check_fixtures_finalized(tid, now=now))
        results.append(check_placeholders_synced(tid, now=now))
    if tier == "MONEY" and live:
        results.append(check_live_gates_ready())
    return results


def _line(prefix: str, r: PreconditionResult) -> str:
    tail = f" → {r.remedy_cmd}" if r.remedy_cmd else ""
    tid = f"[{r.tournament_id}] " if r.tournament_id else ""
    return f"  {prefix}: {tid}{r.detail}{tail}"


def enforce(tier: str, *, tournaments: list[str] | None = None, force: bool = False,
            reason: str | None = None, live: bool = False) -> None:
    results = evaluate(tier, tournaments, live=live)
    for r in results:
        if r.ok is None:
            print(_line("aviso (no verificable)", r))
        elif r.severity == "advisory" and r.ok is False:
            print(_line("aviso", r))
    violations = [r for r in results if r.is_violation]
    if not violations:
        return
    prefix = "BLOQUEO" if tier == "MONEY" else "DATOS VIEJOS"
    for r in violations:
        print(_line(prefix, r))
    if tier != "MONEY":
        print("  (tier lectura: se continúa igual — refrescá para números correctos)")
        return
    if not force:
        print('  Acción de dinero BLOQUEADA. Refrescá y reintentá, o forzá: --force --reason "..."')
        raise SystemExit(2)
    if not reason:
        print("  --force requiere --reason.")
        raise SystemExit(2)
    print(f"  FORZADO por CIO: {reason}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_preconditions_enforce.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add core/preconditions.py tests/unit/test_preconditions_enforce.py
git commit -m "feat: evaluate() + enforce() (escalonado por tier, live-aware)"
```

---

### Task 5: CLI `check_freshness.py`

**Files:**
- Create: `scripts/check_freshness.py`
- Test: `tests/unit/test_check_freshness_cli.py`

**Interfaces:**
- Consumes: `core.preconditions.evaluate`.
- Produces: función `run(as_json: bool = False) -> int` que imprime y devuelve **exit code** (0 si no hay violación mandatoria, 2 si la hay). `main()` llama `sys.exit(run(...))`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_check_freshness_cli.py
import importlib

from core.schemas.precondition import PreconditionResult


def _load(monkeypatch, results):
    mod = importlib.import_module("scripts.check_freshness")
    monkeypatch.setattr(mod.pc, "evaluate", lambda *a, **k: results)
    return mod


def test_exit_zero_when_clean(monkeypatch, capsys):
    mod = _load(monkeypatch, [PreconditionResult(name="fixtures_finalized", ok=True,
                                                 severity="mandatory", tournament_id="wc")])
    assert mod.run(as_json=False) == 0


def test_exit_two_on_violation(monkeypatch):
    mod = _load(monkeypatch, [PreconditionResult(name="fixtures_finalized", ok=False,
                                                 severity="mandatory", tournament_id="wc",
                                                 detail="1 sin finalizar")])
    assert mod.run(as_json=False) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_check_freshness_cli.py -q`
Expected: FAIL (`ModuleNotFoundError: scripts.check_freshness`).

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python
"""check_freshness.py — reporta el estado de las precondiciones de datos.

    python scripts/check_freshness.py          # resumen legible
    python scripts/check_freshness.py --json    # JSON (cron/hooks)

Exit code 2 si hay alguna violación mandatoria; 0 si no. Read-only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8  # noqa: E402

enable_utf8()

import core.preconditions as pc  # noqa: E402


def run(as_json: bool = False) -> int:
    results = pc.evaluate("READ")
    violations = [r for r in results if r.is_violation]
    if as_json:
        print(json.dumps({
            "ok": not violations,
            "results": [r.model_dump(mode="json") for r in results],
        }, indent=2, default=str))
    else:
        print("\n=== Frescura de datos (torneos activos) ===")
        if not results:
            print("  (no hay torneos activos por fecha)")
        for r in results:
            mark = {True: "OK ", False: "!! ", None: "?? "}[r.ok]
            tid = f"[{r.tournament_id}] " if r.tournament_id else ""
            print(f"  {mark}{r.name}: {tid}{r.detail}")
            if r.remedy_cmd and r.ok is not True:
                print(f"        → {r.remedy_cmd}")
        print(f"\n  {'TODO AL DÍA' if not violations else 'HAY DATOS VIEJOS — refrescá antes de operar'}\n")
    return 0 if not violations else 2


def main() -> None:
    ap = argparse.ArgumentParser(description="Estado de precondiciones de datos.")
    ap.add_argument("--json", action="store_true")
    sys.exit(run(ap.parse_args().json))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_check_freshness_cli.py -q`
Expected: PASS (2 tests). Luego correr el CLI real: `python scripts/check_freshness.py` (imprime el estado de WC/Liga MX).

- [ ] **Step 5: Commit**

```bash
git add scripts/check_freshness.py tests/unit/test_check_freshness_cli.py
git commit -m "feat: CLI check_freshness (texto/JSON + exit code)"
```

---

### Task 6: Hook `SessionStart`

**Files:**
- Create: `.claude/settings.json`

**Interfaces:**
- Consumes: `scripts/check_freshness.py` (Task 5).
- Produces: hook que corre el CLI al iniciar sesión; su stdout entra al contexto del agente.

- [ ] **Step 1: Crear el archivo**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "python scripts/check_freshness.py" }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Verificar manualmente**

Run: `python scripts/check_freshness.py; echo "exit=$?"`
Expected: imprime el bloque "Frescura de datos" y `exit=0` (o `exit=2` si hay fixtures viejos). El hook no se puede unit-testear; esta corrida valida el comando exacto que ejecutará.

- [ ] **Step 3: Commit**

```bash
git add .claude/settings.json
git commit -m "feat: hook SessionStart -> check_freshness (aviso de datos viejos por sesion)"
```

---

### Task 7: Guards en acciones de lectura (`account.py`, `scan_market.py`)

**Files:**
- Modify: `scripts/account.py` (dentro de `run()`, antes de imprimir/computar)
- Modify: `scripts/scan_market.py` (en `main()`, tras parsear args, antes del scan)

**Interfaces:**
- Consumes: `core.preconditions.enforce`.
- Produces: nada nuevo (efecto: aviso de frescura).

- [ ] **Step 1: `scripts/account.py`** — agregar import y llamada. Tras la línea `from portfolio.functions.account_source import PolymarketAccountSource` (bloque de imports) agregar:

```python
from core.preconditions import enforce as enforce_freshness
```

Dentro de `run(...)`, como primera línea del cuerpo (antes de `client = LocalStateClient(...)`):

```python
    # PnL/cuenta transversal → evalúa TODOS los torneos activos (aviso, no bloquea).
    enforce_freshness("READ")
```

- [ ] **Step 2: `scripts/scan_market.py`** — agregar el import junto a los demás de negocio y, en `main()` tras parsear args (antes de ejecutar el scan), llamar con el torneo escaneado:

```python
from core.preconditions import enforce as enforce_freshness
...
    enforce_freshness("READ", tournaments=[args.tournament])
```

(usar el nombre real del arg de torneo en `scan_market.py`; es `--tournament` con default `fifa_world_cup_2026`).

- [ ] **Step 3: Verificar**

Run: `python scripts/account.py --closed 5 2>&1 | head -5`
Expected: antes del bloque de cuenta aparece (si hay datos viejos) el aviso `aviso`/`BLOQUEO`→ pero al ser READ **continúa** y muestra la cuenta. Si todo está al día, no imprime avisos.

Run: `python scripts/scan_market.py --hours 24 2>&1 | head -5`
Expected: corre el scan; si hay datos viejos, avisa y sigue.

- [ ] **Step 4: Commit**

```bash
git add scripts/account.py scripts/scan_market.py
git commit -m "feat: guard de frescura (READ, avisa) en account.py y scan_market.py"
```

---

### Task 8: Guards en acciones de dinero (`propose_bet.py`, `place_bets.py`, `orders.py`) + `--force/--reason`

**Files:**
- Modify: `scripts/propose_bet.py`, `scripts/place_bets.py`, `scripts/orders.py`

**Interfaces:**
- Consumes: `core.preconditions.enforce`.
- Produces: flags `--force` (store_true) y `--reason` (str) en cada script; llamada `enforce("MONEY", ...)`.

- [ ] **Step 1: En cada uno de los 3 scripts**, agregar al `ArgumentParser`:

```python
    ap.add_argument("--force", action="store_true",
                    help="fuerza la acción pese a datos viejos (requiere --reason)")
    ap.add_argument("--reason", default=None, help="justificación del --force (queda en el log)")
```

- [ ] **Step 2: Agregar el import y la llamada** al inicio del cuerpo que ejecuta la acción (tras parsear args). Import:

```python
from core.preconditions import enforce as enforce_freshness
```

Llamada — `propose_bet.py` (no va live por sí mismo) y `place_bets.py`/`orders.py` (pasan `live=args.live`):

```python
# propose_bet.py — pasar el torneo si el script lo conoce; si no, None (todos los activos):
enforce_freshness("MONEY", tournaments=_tournaments_for(args), force=args.force, reason=args.reason)

# place_bets.py / orders.py:
enforce_freshness("MONEY", force=args.force, reason=args.reason, live=args.live)
```

Donde `_tournaments_for(args)` devuelve `[args.tournament]` si el script tiene ese arg, o `None`. Si `propose_bet.py` no expone `--tournament`, usar `None` directamente (evalúa todos los activos) — no inventar un arg nuevo.

- [ ] **Step 3: Verificar el bloqueo** (con una DB de torneo activo que tenga un fixture viejo, o forzando el escenario):

Run: `python scripts/propose_bet.py --market "Will X win on 2026-07-20?" --stake 5 --model-prob 0.5 --reason "test" --dry-run; echo "exit=$?"`
Expected: si hay datos viejos → imprime `BLOQUEO ... → update_results ...` y `exit=2`. Con `--force --reason "..."` → imprime `FORZADO por CIO` y procede. Si todo al día → procede normal.

- [ ] **Step 4: Commit**

```bash
git add scripts/propose_bet.py scripts/place_bets.py scripts/orders.py
git commit -m "feat: guard de frescura (MONEY, hard-block + --force/--reason) en scripts de dinero"
```

---

### Task 9: Nota en CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (en el paso 5 del "Protocolo de sesión")

**Interfaces:** ninguna (documentación).

- [ ] **Step 1: Editar** el paso 5 del protocolo para apuntar que la frescura ahora está enforced. Tras el bloque de comandos de refresco, agregar:

```markdown
   **Enforced (2026-07-17):** el hook `SessionStart` corre `scripts/check_freshness.py`
   al arrancar y avisa si hay datos viejos; las acciones de dinero (`propose_bet`,
   `place_bets`, `orders`) **se bloquean** ante `fixtures_finalized` incumplido salvo
   `--force --reason`. Diseño: `docs/superpowers/specs/2026-07-17-mandatory-dependency-hooks-design.md`;
   referencia: `docs/dependency-hooks.html`.
```

- [ ] **Step 2: Correr el suite completo**

Run: `python -m pytest tests/unit -q`
Expected: PASS (todo, incl. los nuevos test_precondition*/test_check_freshness).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: protocolo de sesion apunta a la frescura enforced (hooks + guards)"
```

---

## Notas de verificación final

- `python scripts/check_freshness.py` refleja el estado real de WC 2026 + Liga MX.
- `python scripts/account.py` avisa pero muestra la cuenta (READ).
- Un `propose_bet`/`orders` con datos viejos se bloquea con exit≠0 y da el comando de remedio.
- `python -m pytest tests/unit -q` en verde.
