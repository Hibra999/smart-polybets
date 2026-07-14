#!/usr/bin/env python
"""Retro-registra en el ledger (LocalState) las apuestas manuales ya colocadas.

Las 7 operaciones manuales previas al carril CIO-override (5 totales O/U + 2
ganador de semifinales) se ejecutaron por broker directo y NO quedaron en el
ledger. Este script las asienta como decisiones `executed` con
`strategy_id="manual_override"` y `backfill: true`, tomando condition_id /
token_id / precio / shares REALES de la cuenta live (data API), y matcheándolas
por (título, outcome) contra el registro estático de abajo.

IDEMPOTENTE: `save_decision` no pisa claves existentes; re-correrlo no duplica.

    python scripts/backfill_manual_trades.py           # dry-run (muestra qué haría)
    python scripts/backfill_manual_trades.py --apply   # escribe el ledger

Diseño: docs/superpowers/specs/2026-07-14-cio-override-lane-design.md
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8
from core.env import load_env

enable_utf8()
load_env(Path(__file__).resolve().parent.parent / ".env")

from core.local_state import LocalStateClient
from core.utils import make_idempotency_key
from portfolio.functions.account_source import PolymarketAccountSource

TID = "fifa_world_cup_2026"
STRATEGY_ID = "manual_override"
STRATEGY_VERSION = "1.0"

# (título live, outcome, fecha_operación, nota, extra) — las 7 operaciones manuales
# conocidas. Fechas de totales = fecha del partido (aprox.; sin timestamp en findings).
# extra: participant_home/away (display), event_id + pick_side (autogradea contra el
# fixture al terminar), resolution ("LOST": ya resuelta en la cuenta; pnl = -stake).
KNOWN_MANUAL_OPS = [
    ("England vs. Ghana: O/U 2.5",        "Over",  "2026-07-05", "total R16; ver finding 2026-07-09-totals",
     {"participants": ("England", "Ghana"), "resolution": "LOST"}),
    ("Paraguay vs. France: O/U 2.5",      "Over",  "2026-07-07", "total R16; ver finding 2026-07-09-totals",
     {"participants": ("Paraguay", "France"), "resolution": "LOST"}),
    ("Norway vs. England: O/U 2.5",       "Over",  "2026-07-09", "total QF via place_totals_qf.py",
     {"participants": ("Norway", "England"), "resolution": "LOST"}),
    ("Argentina vs. Switzerland: O/U 2.5", "Over", "2026-07-09", "total QF via place_totals_qf.py",
     {"participants": ("Argentina", "Switzerland"), "resolution": "LOST"}),
    ("Spain vs. Belgium: O/U 2.5",        "Under", "2026-07-09", "total QF via place_totals_qf.py",
     {"participants": ("Spain", "Belgium"), "resolution": "LOST"}),
    ("Will Spain win on 2026-07-14?",     "Yes",   "2026-07-13", "SF via place_winner_sf.py; finding 2026-07-14-sf-winner-bets-live",
     {"participants": ("France", "Spain"), "event_id": "wc_149", "pick_side": "AWAY_WIN",
      "pick_participant": "Spain", "kickoff": "2026-07-14T19:00:00+00:00"}),
    ("Will Argentina win on 2026-07-15?", "Yes",   "2026-07-13", "SF via place_winner_sf.py; finding 2026-07-14-sf-winner-bets-live",
     {"participants": ("England", "Argentina"), "event_id": "wc_150", "pick_side": "AWAY_WIN",
      "pick_participant": "Argentina", "kickoff": "2026-07-15T19:00:00+00:00"}),
]


def live_positions_by_title() -> dict[tuple[str, str], dict]:
    """Posiciones de la cuenta (abiertas + resueltas sin redimir) por (title, outcome)."""
    src = PolymarketAccountSource()
    out: dict[tuple[str, str], dict] = {}
    for p in src.get_positions():
        d = p.model_dump(mode="json") if hasattr(p, "model_dump") else dict(p)
        out[(d.get("title", ""), d.get("outcome", ""))] = d
    return out


def build_payload(pos: dict, *, outcome: str, op_date: str, note: str,
                  extra: dict) -> dict:
    entry = Decimal(str(pos.get("avg_entry_price") or pos.get("avg_price") or 0))
    shares = Decimal(str(pos.get("size_shares") or pos.get("size") or 0))
    stake = (entry * shares).quantize(Decimal("0.01"))
    condition_id = pos["condition_id"]
    key = make_idempotency_key(condition_id, outcome, STRATEGY_ID, STRATEGY_VERSION, op_date)
    home, away = extra.get("participants", ("?", "?"))
    payload = {
        "idempotency_key": key,
        "tournament_id": TID,
        "sport": "football",
        "strategy_id": STRATEGY_ID,
        "strategy_version": STRATEGY_VERSION,
        "condition_id": condition_id,
        "outcome": outcome,
        "pick_side": extra.get("pick_side"),
        "pick_participant": extra.get("pick_participant"),
        "verdict": "REVIEW",
        "recommended_size": str(stake),
        "edge": "0",
        "status": "executed",
        "backfill": True,
        "backfill_note": note,
        "opportunity_json": {
            "polymarket_condition_id": condition_id,
            "polymarket_token_id": str(pos.get("token_id", "")),
            "outcome": outcome,
            "title": pos.get("title"),
            "participant_home": home,
            "participant_away": away,
            "event_id": extra.get("event_id"),
            "event_start_utc": extra.get("kickoff"),
            "best_ask": str(entry),
            "entry_price": str(entry),
            "size_shares": str(shares),
            "trade_date": op_date,
        },
        "order_result": {"status": "live", "note": "backfill desde cuenta live",
                         "filled_size_usdc": str(stake), "price": str(entry)},
    }
    if extra.get("resolution") == "LOST":
        payload["resolution"] = {"outcome": "LOST", "pnl": str(-stake)}
    return payload


def run(apply: bool, state_path: str) -> None:
    client = LocalStateClient(state_path)
    positions = live_positions_by_title()
    print(f"\n=== Backfill de operaciones manuales → ledger ({'APPLY' if apply else 'dry-run'}) ===\n")
    done = missing = skipped = 0
    for title, outcome, op_date, note, extra in KNOWN_MANUAL_OPS:
        pos = positions.get((title, outcome))
        if pos is None:
            print(f"  [MISS]  {title} [{outcome}] — no está en la cuenta live")
            missing += 1
            continue
        payload = build_payload(pos, outcome=outcome, op_date=op_date, note=note,
                                extra=extra)
        key = payload["idempotency_key"]
        if client.check_idempotency(key) is not None:
            print(f"  [SKIP]  {title} [{outcome}] — ya en ledger ({key[:10]})")
            skipped += 1
            continue
        print(f"  [{'ADD' if apply else 'add'}]   {title} [{outcome}] "
              f"stake=${payload['recommended_size']} key={key[:10]}")
        if apply:
            client.save_decision(payload)
            done += 1
    print(f"\n  Resumen: {done} asentadas · {skipped} ya existían · {missing} no encontradas")
    if not apply:
        print("  (dry-run: nada escrito. Aplicar con --apply)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--state", default="data/agent_state.json")
    a = ap.parse_args()
    run(a.apply, a.state)


if __name__ == "__main__":
    main()
