#!/usr/bin/env python
"""Editorial del dia con comentarios del CIO + nota YOLO en picks elegidos.

Computa las sugerencias (cuotas live), anota los partidos que el CIO decidio
apostar por conviccion (hay edge pero el consenso de modelos es debil), los marca
en REVIEW con un badge YOLO, y regenera el HTML.

    POLYMARKET_PRIVATE_KEY=... python scripts/editorial_daily_notes.py --date 2026-06-21
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from agent.workflows import daily_suggestions
from editorial.functions import build_daily_html, save_report
from research.functions import PolymarketLiveSource

TID = "fifa_world_cup_2026"

# Comentarios del CIO por fixture: apuestas de conviccion (solo edge, riesgosas).
# Directriz: hay edge pero el consenso de modelos es debil -> YOLO.
NOTES = {
    "wc_87": {
        "yolo": True,
        "cio_note": (
            "Apostado 30 pUSD por directriz del CIO. Hay edge (+14.2%) pero Bayes "
            "y TrueSkill no acompanan al Elo: apuesta de conviccion, no de consenso. "
            "Solo edge, alto riesgo. YOLO."
        ),
    },
    "wc_88": {
        "yolo": True,
        "cio_note": (
            "Apostado 30 pUSD por directriz del CIO. Hay edge (+17.0%) pero el "
            "consenso de modelos es debil (Bayes por debajo del mercado). Solo edge, "
            "alto riesgo. YOLO."
        ),
    },
}


def run(date: str, bankroll: float) -> None:
    data = daily_suggestions.compute(
        date, TID, market_source=PolymarketLiveSource(), bankroll=bankroll,
        source_name="polymarket-live",
    )
    annotated = 0
    for row in data["rows"]:
        note = NOTES.get(row.get("fixture_id"))
        if not note:
            continue
        row["cio_note"] = note["cio_note"]
        row["yolo"] = note["yolo"]
        row["verdict"] = "REVIEW"  # apuesta de conviccion: queda en revision, no AUTO
        annotated += 1

    html = build_daily_html(data)
    path = save_report(TID, html, suffix="suggestions", ext="html", date=date)
    print(f"Sugerencias {date}: {len(data['rows'])} partidos, {annotated} con nota del CIO.")
    print(f"HTML: {path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--bankroll", type=float, default=553.72)
    a = ap.parse_args()
    run(a.date, a.bankroll)


if __name__ == "__main__":
    main()
