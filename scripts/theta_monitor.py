#!/usr/bin/env python
"""CLI del theta trade — monitorea la posición, imprime PnL, persiste todo, y vende
al disparo de la regla O por comando manual (hard stop).

COMANDOS EN VIVO (tipear + Enter mientras corre):
    v   VENDER YA (hard stop manual: cierra la posición al best bid, con reintentos)
    p   imprimir resumen de PnL/estado
    q   salir SIN vender (la posición queda abierta)
Ctrl+C = igual que q (sale sin vender, imprime resumen, los datos ya están guardados).

Regla automática (execution/functions/theta_exit.py, pura y testeada):
    TP  PnL ≥ --tp (default +5%) desde el minuto --from-min (default 30)
    HARD venta forzada al minuto --hard-exit-min (default 105)
    STOP opcional con --stop

PERSISTENCIA (cada lectura, pase lo que pase): tablas `theta_session` y
`theta_tick` en data/<torneo>/market_ticks.sqlite (WAL, gitignored). Si la venta
falla, el CLI imprime las últimas lecturas + PnL, guarda el error y REINTENTA
(hasta 3 veces con bid fresco); si aun así falla, deja instrucciones y todos los
datos quedan en la DB.

SEGURO POR DEFECTO: dry-run. Venta real: --live + POLYMARKET_LIVE=1 + key +
kill-switch off + confirmación tipeada AL INICIO (al disparo importa la velocidad).

    python scripts/theta_monitor.py --market "Will Club Necaxa win on 2026-07-16?" \
        --entry 0.48 --shares 40                       # dry-run
    python scripts/theta_monitor.py --market "…" --entry 0.46 --shares 40 --live

⚠️ La venta manual NO queda en el ledger: asentarla con backfill_manual_trades.py.
Finding: docs/findings/2026-07-14-theta-trade-lay-favorito.md
"""
from __future__ import annotations

import argparse
import queue
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8
from core.env import load_env

enable_utf8()
load_env(Path(__file__).resolve().parent.parent / ".env")

from core.types import OrderSide, OrderType
from core.utils import to_decimal
from execution.functions.broker import PolymarketBroker
from execution.functions.theta_exit import ThetaExitConfig, evaluate_exit
from execution.schemas.trade_order import TradeOrder
from tournaments.registry import get_config
from venue.books import best_prices, order_book
from venue.discovery import match_events

REPO = Path(__file__).resolve().parent.parent
SELL_RETRIES = 3

DDL = """
CREATE TABLE IF NOT EXISTS theta_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT, ended_at TEXT,
    market TEXT, token_id TEXT, kickoff_utc TEXT,
    entry_price REAL, shares REAL,
    tp_pct REAL, from_min REAL, hard_exit_min REAL, stop_pct REAL,
    live INTEGER,
    exit_reason TEXT, exit_price REAL, pnl_usdc REAL,
    order_id TEXT, order_status TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS theta_tick (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER, ts_utc TEXT, minute REAL,
    best_bid REAL, best_ask REAL, bid_size REAL,
    pnl_pct REAL, pnl_usdc REAL, action TEXT, note TEXT
);
CREATE INDEX IF NOT EXISTS idx_theta_tick_session ON theta_tick(session_id, ts_utc);
"""


class SessionStore:
    """Persistencia de la sesión de trading (WAL: sobrevive a cualquier corte)."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(db_path)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript(DDL)
        self.session_id: int | None = None

    def open_session(self, **kw) -> int:
        cols = ",".join(kw)
        cur = self.con.execute(
            f"INSERT INTO theta_session({cols}) VALUES({','.join('?'*len(kw))})",
            tuple(kw.values()))
        self.con.commit()
        self.session_id = cur.lastrowid
        return self.session_id

    def tick(self, **kw) -> None:
        kw["session_id"] = self.session_id
        cols = ",".join(kw)
        self.con.execute(
            f"INSERT INTO theta_tick({cols}) VALUES({','.join('?'*len(kw))})",
            tuple(kw.values()))
        self.con.commit()

    def close_session(self, **kw) -> None:
        sets = ",".join(f"{k}=?" for k in kw)
        self.con.execute(f"UPDATE theta_session SET {sets} WHERE id=?",
                         (*kw.values(), self.session_id))
        self.con.commit()


def command_listener(q: "queue.Queue[str]") -> None:
    """Thread daemon: lee comandos de stdin sin bloquear el loop."""
    for line in sys.stdin:
        q.put(line.strip().lower())


def _norm(s: str) -> str:
    """Comparación insensible a mayúsculas Y acentos ('juarez' matchea 'Juárez')."""
    import unicodedata
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def resolve_market(question_query: str, tag_id: int):
    for me in match_events(tag_id=tag_id, closed=False):
        for m in me.event.markets:
            d = m.model_dump()
            mq = d.get("question") or ""
            if _norm(question_query) in _norm(mq) and mq.startswith("Will "):
                no = (d.get("outcomes") or {}).get("no") or {}
                tick = to_decimal((d.get("trading") or {}).get("minimum_tick_size") or "0.001")
                return str(no.get("token_id") or ""), tick, me.kickoff, mq
    return None, None, None, None


def list_markets(tag_id: int, query: str | None = None) -> None:
    """Muestra los mercados winner abiertos del torneo con sus tokens y precios,
    para elegir el --market (o el --token NO directo). Cómo obtener el id."""
    print(f"\n{'KICKOFF (UTC)':17s} {'QUESTION':52s} {'YES bid/ask':12s} TOKEN NO (para --token)")
    print("-" * 118)
    rows = []
    for me in match_events(tag_id=tag_id, closed=False):
        if not me.has_winner_market:
            continue
        for m in me.event.markets:
            d = m.model_dump()
            q = d.get("question") or ""
            if not q.startswith("Will ") or " win " not in q:
                continue
            if query and _norm(query) not in _norm(q):
                continue
            p = d.get("prices") or {}
            no = (d.get("outcomes") or {}).get("no") or {}
            rows.append((me.kickoff, q, p.get("best_bid"), p.get("best_ask"),
                         str(no.get("token_id") or "")))
    for ko, q, bb, ba, tok in sorted(rows, key=lambda r: (r[0] is None, r[0])):
        ko_s = ko.strftime("%m-%d %H:%M") if ko else "?"
        print(f"{ko_s:17s} {q[:52]:52s} {str(bb):5s}/{str(ba):5s}  {tok}")
    print(f"\n{len(rows)} mercados. Usá --market \"<substring de la question>\" "
          f"(recomendado) o --token <TOKEN NO> --kickoff <ISO>.")


def try_sell(broker, token, shares, tick, action, store) -> tuple[object | None, float | None]:
    """Vende con reintentos (bid fresco en cada intento). (result, fill_bid)."""
    for attempt in range(1, SELL_RETRIES + 1):
        try:
            bb, ba, bsz = best_prices(order_book(token))
            if bb is None:
                raise RuntimeError("book sin bids")
            order = TradeOrder(
                condition_id="", token_id=token, outcome=f"THETA EXIT {action}",
                side=OrderSide.SELL, order_type=OrderType.LIMIT,
                price=to_decimal(bb), size_usdc=to_decimal(shares) * to_decimal(bb),
                size_shares=to_decimal(shares), tif="GTC", tick_size=tick,
            )
            res = broker.place(order)
            store.tick(ts_utc=_now_iso(), minute=None, best_bid=bb, best_ask=ba,
                       bid_size=bsz, pnl_pct=None, pnl_usdc=None,
                       action=f"SELL_{action}", note=f"intento {attempt}: {res.status}")
            if res.status in ("live", "dry_run"):
                return res, bb
            print(f"  [!] intento {attempt}/{SELL_RETRIES}: status={res.status} "
                  f"{res.raw.get('error') or ''} — reintento…")
        except Exception as exc:  # noqa: BLE001 — el cierre NUNCA muere sin registrar
            print(f"  [!] intento {attempt}/{SELL_RETRIES} falló: {exc}")
            store.tick(ts_utc=_now_iso(), minute=None, best_bid=None, best_ask=None,
                       bid_size=None, pnl_pct=None, pnl_usdc=None,
                       action=f"SELL_{action}_ERROR", note=str(exc)[:200])
        time.sleep(1.5)
    return None, None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def summary(entry, shares, last_bid, n_ticks, reason) -> str:
    if last_bid is not None:
        pnl = (last_bid - entry) * shares
        pct = (last_bid - entry) / entry
        val = f"PnL (al último bid {last_bid}): {pnl:+.2f} USDC ({pct:+.1%})"
    else:
        val = "PnL: sin bid de referencia"
    return (f"\n  ── RESUMEN ─ {reason} ─\n"
            f"  lecturas: {n_ticks} · entry {entry} × {shares} shares · {val}\n"
            f"  datos guardados en theta_session/theta_tick (market_ticks.sqlite)")


def main() -> None:
    ap = argparse.ArgumentParser(description="CLI del theta trade (monitor + hard stop).")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--list", nargs="?", const="", default=None, metavar="FILTRO",
                   help="listar mercados abiertos del torneo (con tokens y precios) y salir")
    g.add_argument("--market", help="question del mercado winner (substring); usa el token NO")
    g.add_argument("--token", help="token_id directo de la posición (cualquier mercado de PM)")
    ap.add_argument("--entry", type=float, help="precio de entrada del NO")
    ap.add_argument("--shares", type=float, help="shares de NO a vender")
    ap.add_argument("--kickoff", default=None, help="ISO UTC; obligatorio con --token")
    ap.add_argument("--tp", type=float, default=0.05)
    ap.add_argument("--from-min", type=float, default=30.0)
    ap.add_argument("--hard-exit-min", type=float, default=105.0)
    ap.add_argument("--stop", type=float, default=None)
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--tournament", default="liga_mx_2026")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--confirm", default=None)
    a = ap.parse_args()

    if a.list is not None:
        tag = get_config(a.tournament).polymarket_tag_id
        list_markets(tag, a.list or None)
        return
    if not (a.market or a.token):
        ap.error("se requiere --market o --token (o --list para descubrir mercados)")
    if a.entry is None or a.shares is None:
        ap.error("--entry y --shares son obligatorios para monitorear")

    cfg = ThetaExitConfig(tp_pct=a.tp, from_min=a.from_min,
                          hard_exit_min=a.hard_exit_min, stop_pct=a.stop)
    if a.market:
        tag = get_config(a.tournament).polymarket_tag_id
        token, tick, kickoff, q = resolve_market(a.market, tag)
        if not token:
            print(f"mercado no encontrado: {a.market}")
            return
    else:
        token, tick, q = a.token, to_decimal("0.001"), "(token directo)"
        if not a.kickoff:
            print("--token requiere --kickoff (ISO UTC)")
            return
        kickoff = datetime.fromisoformat(a.kickoff.replace("Z", "+00:00"))

    broker = PolymarketBroker(live=a.live)
    mode = "LIVE ⚠️ venta AUTOMÁTICA al disparo" if broker.live else \
        f"DRY-RUN ({broker._blocked_reason or 'flag off'})"
    print(f"mercado: {q}\ntoken NO: {token[:24]}…  kickoff: {kickoff}\nmodo: {mode}")
    print(f"regla: TP +{cfg.tp_pct:.0%} desde min {cfg.from_min:.0f} · HARD min "
          f"{cfg.hard_exit_min:.0f} · stop {cfg.stop_pct or '—'} · entry {a.entry} × {a.shares}")
    print("comandos: [v]+Enter = VENDER YA · [p]+Enter = PnL · [q]+Enter = salir sin vender\n")

    if broker.live:
        expected = f"{a.shares:g}"
        typed = a.confirm if a.confirm is not None else \
            input(f"    Venta automática armada. Confirmá tipeando las shares ('{expected}'): ")
        if typed.strip() != expected:
            print("    Confirmación incorrecta — abortado.")
            return

    store = SessionStore(REPO / "data" / a.tournament / "market_ticks.sqlite")
    store.open_session(started_at=_now_iso(), market=q, token_id=token,
                       kickoff_utc=kickoff.isoformat(), entry_price=a.entry,
                       shares=a.shares, tp_pct=cfg.tp_pct, from_min=cfg.from_min,
                       hard_exit_min=cfg.hard_exit_min, stop_pct=cfg.stop_pct,
                       live=int(broker.live))

    cmd_q: "queue.Queue[str]" = queue.Queue()
    threading.Thread(target=command_listener, args=(cmd_q,), daemon=True).start()

    last_bid = None
    n_ticks = 0
    exit_reason = "q (sin vender)"
    try:
        while True:
            t0 = time.monotonic()
            now = datetime.now(timezone.utc)
            mins = (now - kickoff).total_seconds() / 60.0

            # ── comandos del operador ────────────────────────────────────
            action = None
            try:
                cmd = cmd_q.get_nowait()
            except queue.Empty:
                cmd = None
            if cmd == "q":
                break
            if cmd == "p":
                print(summary(a.entry, a.shares, last_bid, n_ticks, "estado actual"))
            if cmd == "v":
                action = "MANUAL"
                print("  ★ HARD STOP MANUAL — vendiendo YA")

            # ── lectura + regla (si no hubo comando de venta) ────────────
            if action is None:
                if mins < -2:
                    print(f"  pre-kickoff ({-mins:.0f} min) …", end="\r")
                    time.sleep(min(15.0, max(2.0, -mins * 30)))
                    continue
                try:
                    bb, ba, bsz = best_prices(order_book(token))
                except Exception as exc:  # noqa: BLE001
                    print(f"  [warn] book: {exc}")
                    store.tick(ts_utc=_now_iso(), minute=mins, best_bid=None,
                               best_ask=None, bid_size=None, pnl_pct=None,
                               pnl_usdc=None, action="READ_ERROR", note=str(exc)[:200])
                    time.sleep(a.interval)
                    continue
                last_bid = bb if bb is not None else last_bid
                pnl_pct = (bb - a.entry) / a.entry if bb else None
                pnl_usd = (bb - a.entry) * a.shares if bb else None
                rule_action, reason = evaluate_exit(a.entry, bb, mins, cfg)
                n_ticks += 1
                store.tick(ts_utc=_now_iso(), minute=round(mins, 2), best_bid=bb,
                           best_ask=ba, bid_size=bsz, pnl_pct=pnl_pct,
                           pnl_usdc=pnl_usd, action=rule_action, note=reason)
                pnl_str = f"pnl {pnl_usd:+.2f} ({pnl_pct:+.1%})" if pnl_usd is not None else "pnl n/d"
                print(f"  {now:%H:%M:%S}Z min {mins:5.1f}  bid={bb} (sz {bsz})  "
                      f"{pnl_str}  → {reason}")
                action = rule_action

            # ── venta (regla o manual) con reintentos ────────────────────
            if action:
                res, fill_bid = try_sell(broker, token, a.shares, tick, action, store)
                if res is None:
                    print(summary(a.entry, a.shares, last_bid, n_ticks,
                                  f"VENTA FALLÓ tras {SELL_RETRIES} intentos ({action})"))
                    print("  ⚠️ La posición SIGUE ABIERTA. Revisar con orders.py --list "
                          "y vender manual. Todos los intentos quedaron registrados.")
                    exit_reason = f"{action} — venta fallida"
                    store.close_session(ended_at=_now_iso(), exit_reason=exit_reason,
                                        notes="venta fallida tras reintentos")
                    return
                pnl = (float(fill_bid) - a.entry) * a.shares if fill_bid else None
                print(f"  → {res.status}  order_id={res.order_id}")
                print(summary(a.entry, a.shares, fill_bid, n_ticks, f"VENDIDO ({action})"))
                if res.status == "live":
                    print("  (asentar en el ledger con backfill_manual_trades.py)")
                exit_reason = f"{action} @ {fill_bid}"
                store.close_session(ended_at=_now_iso(), exit_reason=exit_reason,
                                    exit_price=fill_bid, pnl_usdc=pnl,
                                    order_id=str(res.order_id), order_status=res.status)
                return
            time.sleep(max(0.5, a.interval - (time.monotonic() - t0)))
    except KeyboardInterrupt:
        exit_reason = "Ctrl+C (sin vender)"
    finally:
        if store.session_id is not None and exit_reason.endswith("(sin vender)"):
            store.close_session(ended_at=_now_iso(), exit_reason=exit_reason)
            print(summary(a.entry, a.shares, last_bid, n_ticks,
                          f"{exit_reason} — LA POSICIÓN SIGUE ABIERTA"))


if __name__ == "__main__":
    main()
