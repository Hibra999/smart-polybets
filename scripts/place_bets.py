#!/usr/bin/env python
"""Colocación automática de apuestas para los partidos de una fecha.

Corre el pipeline AUTO de punta a punta sobre los partidos programados de un día,
usando cuotas LIVE de Polymarket (Gamma) y el broker del CLOB. Idempotente (estado
local: no re-apuesta). SEGURO POR DEFECTO: dry-run (no envía nada real).

    # dry-run (no toca la wallet) — muestra qué se colocaría
    python scripts/place_bets.py --date 2026-06-20

    # ejecución REAL (requiere credenciales + POLYMARKET_LIVE=1 en el entorno)
    python scripts/place_bets.py --date 2026-06-20 --live

Veredictos: AUTO = se coloca; REVIEW = requiere aprobación humana (no se coloca);
DISCARD/SKIP = no se opera. En dry-run, los AUTO muestran la orden simulada.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from adapters.football.db_reader import FootballDBReader
from agent.workflows import full_analysis
from core.local_state import LocalStateClient
from execution.functions import PolymarketBroker
from research.functions import PolymarketLiveSource

TID = "fifa_world_cup_2026"


def run(date: str, bankroll: float, live: bool, state_path: str) -> None:
    reader = FootballDBReader(TID)
    fixtures = reader.query(
        "SELECT id FROM fixture WHERE status='scheduled' AND kickoff_utc LIKE ? "
        "ORDER BY kickoff_utc",
        (f"{date}%",),
    )
    client = LocalStateClient(state_path, bankroll_usdc=bankroll)
    market_source = PolymarketLiveSource()           # cuotas LIVE de Gamma
    broker = PolymarketBroker(live=live)             # dry-run salvo --live + env + creds

    mode = "LIVE ⚠️" if broker.live else f"DRY-RUN ({broker._blocked_reason or 'flag off'})"
    print(f"\n=== Colocación automática WC {date} — modo: {mode} ===")
    print(f"    bankroll={bankroll:.0f} · estado={state_path} · now={datetime.now(timezone.utc).isoformat(timespec='minutes')}\n")
    if not fixtures:
        print("    (sin partidos programados para esa fecha)")
        return

    placed = reviews = discards = skips = 0
    for f in fixtures:
        decisions = full_analysis.run(
            f["id"], TID, client=client, market_source=market_source, broker=broker,
        )
        for d in decisions:
            mode = d["mode"]
            key = d.get("idempotency_key", "")[:10]
            if mode == "AUTO":
                placed += 1
                res = d.get("result", {})
                raw = res.get("raw", {})
                print(f"  [AUTO]    {f['id']:8} {key} → {res.get('status')} "
                      f"token={str(raw.get('token_id'))[:18]}… price={raw.get('price')} "
                      f"shares={raw.get('shares')} (neg_risk={raw.get('neg_risk')})")
            elif mode == "REVIEW":
                reviews += 1
                print(f"  [REVIEW]  {f['id']:8} {key} → requiere aprobación humana")
            elif mode == "DISCARD":
                discards += 1
                print(f"  [DISCARD] {f['id']:8} {key} → {'; '.join(d.get('reasons', []))[:70]}")
            else:
                skips += 1
                print(f"  [SKIP]    {f['id']:8} {key} → {d.get('reason', '')[:70]}")

    print(f"\n    Resumen: {placed} colocadas · {reviews} a revisar · "
          f"{discards} descartadas · {skips} saltadas")
    if not broker.live and placed:
        print("    (dry-run: nada se envió. Para ejecutar real: --live + credenciales + POLYMARKET_LIVE=1)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--live", action="store_true", help="intenta ejecución REAL (requiere creds + env)")
    ap.add_argument("--state", default="data/agent_state.json")
    a = ap.parse_args()
    run(a.date, a.bankroll, a.live, a.state)


if __name__ == "__main__":
    main()
