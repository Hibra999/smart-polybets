"""Precondiciones de frescura de datos para Liga MX y NFL."""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from core.polymarket_client import is_evm_private_key
from core.schemas.precondition import PreconditionResult
from core.utils import utcnow
from tournaments.registry import TOURNAMENTS

REPO = Path(__file__).resolve().parent.parent
GRACE_MINUTES = 150  # margen para no marcar partidos en juego como 'sin finalizar'

_TRUTHY = ("1", "true", "yes", "on")
_REFRESH_COMMANDS = {
    "liga_mx_2026": (
        "python data/liga_mx_2026/ingest/fetch_fixtures_pm.py --include-closed --apply"
    ),
    "nfl_2026": "python scripts/migrate_nfl_data.py --since 2022",
}


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
    except sqlite3.Error as exc:
        return PreconditionResult(name="fixtures_finalized", ok=None, severity="mandatory",
                                  tournament_id=tid, detail=f"no verificable: {exc}")
    finally:
        con.close()
    ok = n == 0
    return PreconditionResult(
        name="fixtures_finalized", ok=ok, severity="mandatory", tournament_id=tid,
        detail=("datos al día" if ok else f"{n} partido(s) jugado(s) sin finalizar"),
        remedy_cmd=None if ok else f"python scripts/update_results.py --tournament {tid} --apply")


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
    except sqlite3.Error as exc:
        return PreconditionResult(name="placeholders_synced", ok=None, severity="advisory",
                                  tournament_id=tid, detail=f"no verificable: {exc}")
    finally:
        con.close()
    ok = n == 0
    return PreconditionResult(
        name="placeholders_synced", ok=ok, severity="advisory", tournament_id=tid,
        detail=("placeholders al día" if ok else f"{n} fixture(s) próximos con equipo placeholder"),
        remedy_cmd=None if ok else _REFRESH_COMMANDS.get(tid))


def check_live_gates_ready() -> PreconditionResult:
    problems = []
    key = os.getenv("POLYMARKET_PRIVATE_KEY")
    if not key:
        problems.append("falta POLYMARKET_PRIVATE_KEY")
    elif not is_evm_private_key(key):
        problems.append("POLYMARKET_PRIVATE_KEY no es una clave EVM válida")
    if os.getenv("POLYMARKET_LIVE", "") not in _TRUTHY:
        problems.append("POLYMARKET_LIVE!=1")
    if os.getenv("POLYMARKET_KILL_SWITCH", "") in _TRUTHY:
        problems.append("kill-switch activo")
    ok = not problems
    return PreconditionResult(
        name="live_gates_ready", ok=ok, severity="mandatory", tournament_id=None,
        detail=("gates live OK" if ok else "; ".join(problems)),
        remedy_cmd=None if ok else "setear POLYMARKET_LIVE=1 + key y POLYMARKET_KILL_SWITCH=0")


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
