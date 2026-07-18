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
