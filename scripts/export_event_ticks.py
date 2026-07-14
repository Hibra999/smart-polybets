#!/usr/bin/env python
"""Exporta TODO el movimiento de mercado de un evento a su propio SQLite en el repo.

Organización acordada (2026-07-14): la data de mercado queda POR TORNEO Y POR
EVENTO para fácil acceso y análisis posterior:

    data/<tournament>/events/<YYYY-MM-DD>-<home>-vs-<away>/ticks.sqlite

Contenido del export (desde el buffer rodante `market_ticks.sqlite`):
  - `tick`         : snapshots 1/min de TODOS los mercados del evento
                     (bid/ask/last/spread/vol/liquidez + book depth + score live)
  - `theta_tick`   : capturas finas (5s) de los monitores que tocaron tokens del evento
  - `theta_session`: sesiones de trading/captura asociadas
  - `meta`         : evento, kickoff, rango temporal, filas, exported_at

El buffer rodante sigue gitignored (crece sin límite); los exports por evento SÍ
se versionan (dataset finito y cerrado). IDEMPOTENTE: re-exportar reescribe el
archivo (correr de nuevo al terminar el partido para el dataset completo).

    python scripts/export_event_ticks.py --event "France vs. Spain"
    python scripts/export_event_ticks.py --tournament liga_mx_2026 --all   # post-jornada
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()

REPO = Path(__file__).resolve().parent.parent

META_DDL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY, value TEXT
);
"""


def slugify(title: str, kickoff: str | None) -> str:
    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "-", t.lower().replace(" vs. ", "-vs-")).strip("-")
    date = (kickoff or "")[:10] or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{date}-{t}"


def export_event(src: sqlite3.Connection, tid: str, title: str) -> Path | None:
    rows = src.execute(
        "SELECT * FROM tick WHERE title = ? ORDER BY id", (title,)).fetchall()
    if not rows:
        print(f"  [MISS] sin ticks para: {title}")
        return None
    cols = [d[0] for d in src.execute("SELECT * FROM tick LIMIT 1").description]
    kickoff = rows[0][cols.index("kickoff_utc")]
    tokens = {r[cols.index("token_id")] for r in rows if r[cols.index("token_id")]}

    out_dir = REPO / "data" / tid / "events" / slugify(title, kickoff)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ticks.sqlite"
    if out_path.exists():
        out_path.unlink()  # idempotente: re-export reescribe

    dst = sqlite3.connect(out_path)
    # mismos schemas que el buffer (copiados del sqlite_master de la fuente)
    for name in ("tick", "theta_tick", "theta_session"):
        ddl = src.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
        if ddl and ddl[0]:
            dst.execute(ddl[0])
    dst.executescript(META_DDL)

    ph = ",".join("?" * len(cols))
    dst.executemany(f"INSERT INTO tick VALUES({ph})", rows)

    n_fine = n_sess = 0
    has_theta = src.execute(
        "SELECT 1 FROM sqlite_master WHERE name='theta_session'").fetchone()
    if has_theta and tokens:
        qmarks = ",".join("?" * len(tokens))
        sess = src.execute(
            f"SELECT * FROM theta_session WHERE token_id IN ({qmarks})",
            tuple(tokens)).fetchall()
        if sess:
            scols = [d[0] for d in src.execute("SELECT * FROM theta_session LIMIT 1").description]
            dst.executemany(
                f"INSERT INTO theta_session VALUES({','.join('?'*len(scols))})", sess)
            n_sess = len(sess)
            sids = [s[scols.index("id")] for s in sess]
            fine = src.execute(
                f"SELECT * FROM theta_tick WHERE session_id IN ({','.join('?'*len(sids))})",
                tuple(sids)).fetchall()
            if fine:
                fcols = [d[0] for d in src.execute("SELECT * FROM theta_tick LIMIT 1").description]
                dst.executemany(
                    f"INSERT INTO theta_tick VALUES({','.join('?'*len(fcols))})", fine)
                n_fine = len(fine)

    ts = [r[cols.index("ts_utc")] for r in rows]
    for k, v in (("event", title), ("tournament", tid), ("kickoff_utc", kickoff),
                 ("first_tick", min(ts)), ("last_tick", max(ts)),
                 ("n_ticks", len(rows)), ("n_theta_ticks", n_fine),
                 ("n_theta_sessions", n_sess),
                 ("exported_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))):
        dst.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, str(v)))
    dst.commit()
    dst.close()
    print(f"  [OK] {out_path.relative_to(REPO)}  ({len(rows)} ticks, "
          f"{n_fine} finos, {n_sess} sesiones)")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tournament", default="fifa_world_cup_2026")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--event", help="título del evento (substring, insensible a acentos)")
    g.add_argument("--all", action="store_true", help="exportar todos los eventos del buffer")
    a = ap.parse_args()

    buf = REPO / "data" / a.tournament / "market_ticks.sqlite"
    if not buf.exists():
        print(f"no existe el buffer: {buf}")
        return
    src = sqlite3.connect(buf)

    def norm(s):
        return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()

    titles = [r[0] for r in src.execute("SELECT DISTINCT title FROM tick ORDER BY title")]
    if a.all:
        targets = titles
    else:
        targets = [t for t in titles if norm(a.event) in norm(t)]
        if not targets:
            print(f"sin eventos que matcheen '{a.event}'. Disponibles: {titles}")
            return
    print(f"=== export {a.tournament}: {len(targets)} evento(s) ===")
    for t in targets:
        export_event(src, a.tournament, t)


if __name__ == "__main__":
    main()
