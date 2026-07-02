"""Funciones puras de normalización y matching de nombres de equipos/mercados.

Portado de research/functions/polymarket_live.py (_canon, _ALIASES, _WILL_WIN_RE).
SIN acceso a red — todas las funciones son unit-testeables con objetos fake.

Interface exportada:
  canon(name: str) -> str
  match_event(event, home: str, away: str) -> list[dict] | None
"""
from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

# Alias de nombres (Polymarket/inglés → canónico del proyecto), portado de
# research/functions/polymarket_live.py._ALIASES.
# Clave: ascii-normalizado, sin acentos, minúsculas (con espacios o sin).
# Valor: nombre canónico del proyecto (con espacios, minúsculas).
ALIASES: dict[str, str] = {
    "cote divoire": "ivory coast",
    "cotedivoire": "ivory coast",
    "dr congo": "congo dr",
    "drcongo": "congo dr",
    "bosnia and herzegovina": "bosnia herzegovina",
    "cabo verde": "cape verde",
    "turkey": "turkiye",
    "czech republic": "czechia",
    "south korea": "korea republic",
    "korea": "korea republic",
    "united states": "usa",
    "united states of america": "usa",
}

_WILL_WIN_RE = re.compile(r"\s*will\s+(.+?)\s+win\b", re.I)


def canon(name: str) -> str:
    """Clave de comparación: sin acentos, minúsculas, sólo alfanumérico, con alias.

    Portado de _canon() en research/functions/polymarket_live.py.
    """
    n = unicodedata.normalize("NFKD", (name or "")).encode("ascii", "ignore").decode()
    n = re.sub(r"[^a-z0-9 ]", "", n.lower()).strip()
    n = ALIASES.get(n, n)
    n = ALIASES.get(n.replace(" ", ""), n)
    return n.replace(" ", "")


def _extract_yes_token(market) -> dict | None:
    """Extrae los datos del outcome YES de un Market-like del SDK.

    El SDK produce objetos con:
      market.outcomes.yes.token_id  — token YES
      market.outcomes.yes.price     — precio mid (Decimal)
      market.outcomes.yes.label     — "Yes" / "No" (puede no ser "Yes" si orden invertido)
      market.outcomes.no.{token_id, price, label}
      market.prices.{best_ask, best_bid}
      market.metrics.{volume_num, volume, liquidity_num, liquidity}
      market.state.{neg_risk, accepting_orders}
      market.trading.{minimum_tick_size, minimum_order_size}
      market.condition_id

    Soporta también objetos fake (SimpleNamespace / clases de test) siempre que
    expongan los mismos atributos vía getattr.
    """
    try:
        yes_out = market.outcomes.yes
        no_out = market.outcomes.no
    except AttributeError:
        return None

    # Determinar cuál slot es el YES real (por label)
    yes_label = (getattr(yes_out, "label", "") or "").strip().lower()
    no_label = (getattr(no_out, "label", "") or "").strip().lower()
    if yes_label == "yes":
        token_id = str(getattr(yes_out, "token_id", "") or "")
        yes_price = getattr(yes_out, "price", None)
    elif no_label == "yes":
        # Orden invertido: el slot "no" del SDK tiene el token YES real
        token_id = str(getattr(no_out, "token_id", "") or "")
        yes_price = getattr(no_out, "price", None)
    else:
        return None

    if not token_id:
        return None

    # Precio fallback: si mid es None, intentar best_ask
    prices = getattr(market, "prices", None)
    if yes_price is None:
        yes_price = getattr(prices, "best_ask", None)
    if yes_price is None:
        yes_price = Decimal("0")

    metrics = getattr(market, "metrics", None)
    state = getattr(market, "state", None)
    trading = getattr(market, "trading", None)

    best_ask = getattr(prices, "best_ask", None)
    best_bid = getattr(prices, "best_bid", None)

    # volume: preferir volume_num (USDC float), caer a volume si no
    volume_raw = getattr(metrics, "volume_num", None) or getattr(metrics, "volume", None)
    liquidity_raw = (
        getattr(metrics, "liquidity_num", None) or getattr(metrics, "liquidity", None)
    )
    volume = Decimal(str(volume_raw)) if volume_raw is not None else Decimal("0")
    liquidity = Decimal(str(liquidity_raw)) if liquidity_raw is not None else Decimal("0")

    neg_risk = bool(getattr(state, "neg_risk", False))
    tick_size = getattr(trading, "minimum_tick_size", None)
    min_order_size = getattr(trading, "minimum_order_size", None)
    accepting_orders = bool(getattr(state, "accepting_orders", False))
    condition_id = str(getattr(market, "condition_id", "") or "")

    return {
        "token_id": token_id,
        "condition_id": condition_id,
        "yes_price": Decimal(str(yes_price)),
        "best_ask": best_ask,
        "best_bid": best_bid,
        "volume": volume,
        "liquidity": liquidity,
        "neg_risk": neg_risk,
        "tick_size": tick_size,
        "min_order_size": min_order_size,
        "accepting_orders": accepting_orders,
    }


def match_event(event, home: str, away: str) -> list[dict] | None:
    """Intentar hacer match de un Event-like del SDK contra un fixture home/away.

    El título del evento debe ser del tipo "X vs. Y" (case-insensitive, acentos
    normalizados). Itera sobre los mercados del evento buscando "Will X win?"
    para determinar HOME_WIN / AWAY_WIN.

    Args:
        event:  Objeto con .title (str) y .markets (iterable de Market-like).
        home:   Nombre del equipo local (se canonicaliza internamente).
        away:   Nombre del equipo visitante (se canonicaliza internamente).

    Returns:
        Lista de dicts con info de mercado + model_outcome, o None si el evento
        no corresponde al fixture dado.
    """
    title = str(getattr(event, "title", "") or "")
    # Descartar subtítulo después de " - " (ej: "Netherlands vs. Sweden - WC 2026")
    title = title.split(" - ")[0]

    m = re.match(r"^(.+?)\s+vs\.?\s+(.+?)\??$", title, re.I)
    if not m:
        return None

    ev_home_k = canon(m.group(1))
    ev_away_k = canon(m.group(2))
    req_home_k = canon(home)
    req_away_k = canon(away)

    # El evento coincide si home/away (o su inverso) coinciden canónicamente
    pair_match = (
        (ev_home_k == req_home_k and ev_away_k == req_away_k)
        or (ev_home_k == req_away_k and ev_away_k == req_home_k)
    )
    if not pair_match:
        return None

    results: list[dict] = []
    for mkt in (getattr(event, "markets", None) or []):
        q = str(getattr(mkt, "question", "") or "")
        # Descartar mercados de empate
        if "draw" in q.lower():
            continue
        wm = _WILL_WIN_RE.match(q)
        if not wm:
            continue
        team_k = canon(wm.group(1))

        # Asignar outcome según el par (home, away) de NUESTRA predicción
        if team_k == req_home_k:
            outcome = "HOME_WIN"
        elif team_k == req_away_k:
            outcome = "AWAY_WIN"
        else:
            continue

        info = _extract_yes_token(mkt)
        if info:
            results.append({**info, "model_outcome": outcome})

    return results or None
