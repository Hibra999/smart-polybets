#!/usr/bin/env python
"""Editorial del día: HTML de sugerencias + tweet publicado vía Metricool.

1. Computa las sugerencias del día (modelo vs cuotas Polymarket).
2. Genera un HTML con el design system pypro.mx → editorial/reports/{id}/.
3. Arma el tweet y lo agenda/publica en Metricool.

SEGURO POR DEFECTO: el tweet va en dry-run (no se envía). Para publicar de verdad:
`--publish` con credenciales Metricool en el entorno; `--auto` para que Metricool
lo publique automáticamente (si no, queda agendado para revisión).

    python scripts/editorial_daily.py --date 2026-06-20
    python scripts/editorial_daily.py --date 2026-06-20 --live          # cuotas live
    python scripts/editorial_daily.py --date 2026-06-20 --publish --auto  # publica real
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from agent.tools import publish_tools
from agent.workflows import daily_suggestions
from editorial.functions import build_daily_html, build_daily_tweet, save_report

TID = "fifa_world_cup_2026"


def run(date: str, *, live: bool, publish: bool, auto: bool, bankroll: float) -> None:
    market_source = None
    source_name = "polymarket"
    if live:
        from research.functions import PolymarketLiveSource
        market_source = PolymarketLiveSource()
        source_name = "polymarket-live"

    data = daily_suggestions.compute(
        date, TID, market_source=market_source, bankroll=bankroll, source_name=source_name,
    )
    n = len(data["rows"])
    print(f"Sugerencias {date}: {n} partidos analizados (estrategia {data['strategy']}).")

    # 1. HTML
    html = build_daily_html(data)
    path = save_report(TID, html, suffix="suggestions", ext="html", date=date)
    print(f"HTML: {path}")

    # 2. Tweet
    tweet = build_daily_tweet(data)
    print(f"\nTweet ({len(tweet)} chars):\n{'-' * 50}\n{tweet}\n{'-' * 50}")

    # 3. Publicar vía Metricool
    res = publish_tools.publish_tweet(tweet, auto_publish=auto, dry_run=not publish)
    if res.get("dry_run"):
        print("\nMetricool: DRY-RUN (no se envió). Usá --publish + credenciales para publicar.")
    else:
        print(f"\nMetricool: publicado/agendado (autoPublish={auto}). id="
              f"{res.get('data', {}).get('id')}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--live", action="store_true", help="usar cuotas live de Polymarket")
    ap.add_argument("--publish", action="store_true", help="enviar el tweet a Metricool de verdad")
    ap.add_argument("--auto", action="store_true", help="autoPublish en Metricool")
    a = ap.parse_args()
    run(a.date, live=a.live, publish=a.publish, auto=a.auto, bankroll=a.bankroll)


if __name__ == "__main__":
    main()
