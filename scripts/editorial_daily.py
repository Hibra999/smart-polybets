"""Editorial del día: HTML de sugerencias + tweet publicado vía Metricool.

1. Computa las sugerencias del día (modelo vs cuotas Polymarket).
2. Genera un HTML con el design system pypro.mx → editorial/reports/{id}/.
3. Arma el tweet y lo agenda/publica en Metricool.

SEGURO POR DEFECTO: el tweet va en dry-run (no se envía). Para publicar de verdad:
`--publish` con credenciales Metricool en el entorno; `--auto` para que Metricool
lo publique automáticamente (si no, queda agendado para revisión).

    python scripts/editorial_daily.py --date YYYY-MM-DD --observe-draft
"""
from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from agent.tools import publish_tools
from agent.workflows import daily_suggestions
from editorial.functions import build_daily_html, build_daily_tweet, save_report
from tournaments.registry import get_config

TID = "liga_mx_2026"


def run(
    date: str,
    *,
    tournament_id: str,
    live: bool,
    publish: bool,
    auto: bool,
    bankroll: float,
    observe_draft: bool,
) -> None:
    market_source = None
    source_name = "polymarket"
    if live:
        from research.functions import PolymarketLiveSource
        tag_id = get_config(tournament_id).polymarket_tag_id
        if tag_id is None:
            raise ValueError(f"{tournament_id} no tiene polymarket_tag_id configurado")
        market_source = PolymarketLiveSource(tag_id=tag_id)
        source_name = "polymarket-live"

    data = daily_suggestions.compute(
        date, tournament_id, market_source=market_source, bankroll=bankroll,
        source_name=source_name, allow_draft=observe_draft,
    )
    n = len(data["rows"])
    print(f"Sugerencias {date}: {n} partidos analizados (estrategia {data['strategy']}).")

    # 1. HTML
    html = build_daily_html(data)
    path = save_report(tournament_id, html, suffix="suggestions", ext="html", date=date)
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
    ap.add_argument("--tournament", default=TID)
    ap.add_argument("--date", default=datetime.now(UTC).strftime("%Y-%m-%d"))
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--live", action="store_true", help="usar cuotas live de Polymarket")
    ap.add_argument("--publish", action="store_true", help="enviar el tweet a Metricool de verdad")
    ap.add_argument("--auto", action="store_true", help="autoPublish en Metricool")
    ap.add_argument("--observe-draft", action="store_true")
    a = ap.parse_args()
    run(
        a.date,
        tournament_id=a.tournament,
        live=a.live,
        publish=a.publish,
        auto=a.auto,
        bankroll=a.bankroll,
        observe_draft=a.observe_draft,
    )


if __name__ == "__main__":
    main()
