#!/usr/bin/env python
"""Recorder de ticks de mercado (Polymarket) → SQLite, un snapshot por minuto.

Paso 1 de la validación del theta trade en Liga MX (finding
2026-07-14-theta-trade-lay-favorito): capturar en tiempo real precio (bid/ask/
last/spread), volumen/liquidez, score en vivo, y PROFUNDIDAD del order book
(la ejecutabilidad es el caveat #2 — el precio mostrado no basta, ver Exp 1 del
finding 2026-07-14-ligamx-sesgos-mercado).

Qué guarda, cada `--interval` segundos (default 60):
  - TODOS los mercados winner/draw abiertos del torneo (1 llamada Gamma paginada)
  - + top-of-book y depth top-3 (batch CLOB) SOLO para partidos en la ventana
    activa [kickoff-60min, kickoff+150min] — donde vive el theta trade.

DB: data/<tournament>/market_ticks.sqlite (WAL; append-only; NO se commitea —
está en .gitignore). Robusto: una excepción en un ciclo se loguea y sigue.

    python scripts/record_market_ticks.py                      # loop infinito, 60s
    python scripts/record_market_ticks.py --once               # un ciclo (Task Scheduler)
    python scripts/record_market_ticks.py --interval 30
Cortar con Ctrl+C. Correr en una terminal dedicada durante las jornadas.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()

from tournaments.registry import get_config
from venue.books import order_books
from venue.discovery import match_events
from venue.ticks import book_summary, tick_rows_from_event

REPO = Path(__file__).resolve().parent.parent
BOOK_PRE_MIN = 60    # ventana activa: book desde 60min antes del kickoff
BOOK_POST_MIN = 150  # …hasta 150min después (fin del theta trade)
BOOK_BATCH = 20      # tokens por llamada get_order_books

DDL = """
CREATE TABLE IF NOT EXISTS tick (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_utc       TEXT NOT NULL,
    event_id     TEXT, title TEXT, kickoff_utc TEXT,
    condition_id TEXT, token_id TEXT, question TEXT, market_kind TEXT,
    best_bid REAL, best_ask REAL, last_price REAL, spread REAL,
    volume REAL, liquidity REAL,
    score TEXT, elapsed TEXT, period TEXT, game_status TEXT,
    bid_size REAL, ask_size REAL, bid_depth3 REAL, ask_depth3 REAL
);
CREATE INDEX IF NOT EXISTS idx_tick_token_ts ON tick(token_id, ts_utc);
CREATE INDEX IF NOT EXISTS idx_tick_ts ON tick(ts_utc);
"""

COLS = ("ts_utc,event_id,title,kickoff_utc,condition_id,token_id,question,market_kind,"
        "best_bid,best_ask,last_price,spread,volume,liquidity,"
        "score,elapsed,period,game_status,bid_size,ask_size,bid_depth3,ask_depth3")


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(DDL)
    return con


def in_book_window(row: dict, now: datetime) -> bool:
    if not row["kickoff_utc"]:
        return False
    ko = datetime.fromisoformat(row["kickoff_utc"])
    return ko - timedelta(minutes=BOOK_PRE_MIN) <= now <= ko + timedelta(minutes=BOOK_POST_MIN)


def one_cycle(con: sqlite3.Connection, tag_id: int) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    ts = now.isoformat(timespec="seconds")
    rows: list[dict] = []
    for me in match_events(tag_id=tag_id, closed=False):
        rows.extend(tick_rows_from_event(me, ts))

    # profundidad del book sólo en la ventana activa (batch, vía venue/books)
    active = [r for r in rows if r["token_id"] and in_book_window(r, now)]
    for i in range(0, len(active), BOOK_BATCH):
        chunk = active[i:i + BOOK_BATCH]
        try:
            books = order_books([r["token_id"] for r in chunk])
            for r, b in zip(chunk, books):
                r.update(book_summary(b))
        except Exception as exc:  # noqa: BLE001 — depth es best-effort, el tick vale igual
            print(f"    [warn] order_books: {exc}")

    con.executemany(
        f"INSERT INTO tick({COLS}) VALUES({','.join('?' * len(COLS.split(',')))})",
        [tuple(r[c] for c in COLS.split(",")) for r in rows],
    )
    con.commit()
    return len(rows), len(active)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tournament", default="liga_mx_2026")
    ap.add_argument("--interval", type=int, default=60, help="segundos entre snapshots")
    ap.add_argument("--once", action="store_true", help="un solo ciclo (p/ Task Scheduler)")
    ap.add_argument("--db", default=None)
    a = ap.parse_args()

    cfg = get_config(a.tournament)
    if cfg.polymarket_tag_id is None:
        print(f"{a.tournament} no tiene polymarket_tag_id en el registry.")
        return
    db_path = Path(a.db) if a.db else REPO / "data" / a.tournament / "market_ticks.sqlite"
    con = open_db(db_path)
    print(f"=== recorder {cfg.display_name} → {db_path} (cada {a.interval}s; Ctrl+C corta) ===")

    while True:
        t0 = time.monotonic()
        try:
            n, nb = one_cycle(con, cfg.polymarket_tag_id)
            print(f"  {datetime.now(timezone.utc):%H:%M:%S}Z  ticks={n:3d}  con_book={nb:2d}  "
                  f"({time.monotonic()-t0:.1f}s)")
        except KeyboardInterrupt:
            raise
        except Exception as exc:  # noqa: BLE001 — el recorder no se cae por un ciclo malo
            print(f"  [ERROR ciclo] {exc}")
        if a.once:
            break
        time.sleep(max(1.0, a.interval - (time.monotonic() - t0)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[cortado por el usuario]")
