#!/usr/bin/env python
"""Backtest 'lay del favorito con salida anticipada' (theta trade) — WC 2026.

Estrategia propuesta por el CIO (2026-07-14): en mercados "Will X win" (resuelven
a 90'), comprar el NO del favorito al kickoff y CERRAR la posición vendiendo a
los +X minutos wall-clock, capturando el decaimiento temporal del favorito
mientras el partido siga cerrado — sin llegar a resolución.

Datos: price history REAL de Polymarket (fidelity=1min) de los knockouts del
Mundial 2026 (mercados cerrados). Favorito = mayor precio Yes 5 min antes del
kickoff (mínimo 0.40). PnL por share de NO, precio de historial (sin
spread/fees — ver haircuts en el finding).

    python scripts/wc_theta_trade_backtest.py

Finding: docs/findings/2026-07-14-theta-trade-lay-favorito.md
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()

from venue.books import price_history
from venue.discovery import match_events

EXITS = (30, 60, 90, 105)   # min wall-clock desde kickoff (105 ≈ min 85 de juego)
KO_STAGE_FROM = "06-28"     # fase eliminatoria del WC 2026
MIN_FAV_YES = 0.40


def yes_path(tok: str, ko: int):
    return price_history(tok, start_ts=ko - 900, end_ts=ko + 150 * 60, fidelity=1)


def price_at(path, ts: int):
    best = None
    for t, p in path:
        if t <= ts:
            best = p
        else:
            break
    return best


def run() -> None:
    evs = [me for me in match_events(closed=True)
           if me.has_winner_market and me.kickoff
           and me.kickoff.strftime("%m-%d") >= KO_STAGE_FROM]
    seen = set()
    results = {x: [] for x in EXITS}
    n_used = 0
    for me in evs:
        key = frozenset((me.home_canon, me.away_canon, me.kickoff.strftime("%m%d")))
        if key in seen:
            continue
        seen.add(key)
        toks = {}
        for m in me.event.markets:
            q = m.question or ""
            if q.startswith("Will ") and " win " in q:
                d = m.model_dump()
                toks[q] = str(d["outcomes"]["yes"]["token_id"])
        if len(toks) != 2:
            continue
        ko = int(me.kickoff.timestamp())
        paths = {q: yes_path(t, ko) for q, t in toks.items()}
        entries = {q: price_at(p, ko - 300) for q, p in paths.items()}
        if any(v is None for v in entries.values()):
            continue
        fav_q = max(entries, key=entries.get)
        fav_path = paths[fav_q]
        p_entry_yes = price_at(fav_path, ko)
        if p_entry_yes is None or p_entry_yes < MIN_FAV_YES:
            continue
        no_cost = 1 - p_entry_yes
        n_used += 1
        for x in EXITS:
            p_exit_yes = price_at(fav_path, ko + x * 60)
            if p_exit_yes is None:
                p_exit_yes = fav_path[-1][1]
            results[x].append((me.title, p_entry_yes, p_exit_yes,
                               (1 - p_exit_yes) - no_cost))

    print(f"partidos usados: {n_used}\n")
    for x in EXITS:
        rs = results[x]
        tot = sum(r[3] for r in rs)
        wins = sum(1 for r in rs if r[3] > 0)
        avg = tot / len(rs) if rs else 0
        cost = sum(1 - r[1] for r in rs) / len(rs)
        print(f"salida +{x:3d}min: n={len(rs):2d}  {wins}W-{len(rs)-wins}L  "
              f"PnL medio/share={avg:+.4f}  (~{avg/cost:+.1%} sobre costo)")
    print("\ndetalle salida +90min (ordenado por PnL):")
    for title, pe, px, pnl in sorted(results[90], key=lambda r: r[3]):
        print(f"  {title[:40]:40s} fav_yes {pe:.2f}->{px:.2f}  pnl/share {pnl:+.3f}")


if __name__ == "__main__":
    run()
