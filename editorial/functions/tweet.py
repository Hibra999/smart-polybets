"""Tweet de las sugerencias del día. Función pura.

Resume las mejores señales (mayor edge positivo) en <=280 caracteres. Sin
em-dashes, sin emojis-bullet. Devuelve el texto del tweet (y opcional un thread
con el resto para Metricool `descendants`).
"""
from __future__ import annotations

from typing import Any

TWEET_LIMIT = 280


def _line(row: dict[str, Any]) -> str:
    edge = row.get("edge") or 0.0
    return (f"{row['pick_team']} {edge * 100:+.0f}% "
            f"(modelo {row['model_prob'] * 100:.0f}% vs mercado {row['market_prob'] * 100:.0f}%)")


def build_daily_tweet(data: dict[str, Any], *, max_picks: int = 3) -> str:
    rows = data.get("rows", [])
    # Señales accionables: edge positivo y veredicto no descartado.
    picks = [r for r in rows
             if r.get("edge") is not None and r["edge"] > 0
             and r.get("verdict") in ("AUTO", "REVIEW")]
    picks.sort(key=lambda r: r["edge"], reverse=True)
    picks = picks[:max_picks]

    tournament = data.get("tournament_name", data.get("tournament_id", ""))
    head = f"Señales {tournament} {data.get('date','')} (modelo vs Polymarket):"
    foot = "Análisis cuantitativo, no es consejo financiero."

    if not picks:
        body = "Hoy el modelo no encuentra valor sobre el mercado. Sin señales accionables."
        return _fit(head, [body], foot)

    return _fit(head, [_line(r) for r in picks], foot)


def _fit(head: str, lines: list[str], foot: str) -> str:
    """Arma head + líneas + foot recortando líneas hasta entrar en 280."""
    while lines:
        text = head + "\n\n" + "\n".join(lines) + "\n\n" + foot
        if len(text) <= TWEET_LIMIT:
            return text
        lines = lines[:-1]
    text = head + "\n\n" + foot
    return text[:TWEET_LIMIT]
