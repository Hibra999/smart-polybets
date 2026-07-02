"""Descubrimiento de eventos/partidos de Polymarket vía el SDK (sin scraper Gamma).

Fetch UNIFICADO que reemplaza los loops de `requests` a Gamma que estaban duplicados
en varios scripts (update_results, fix_kickoffs, sync_upcoming_fixtures). Todo pasa por
el `PublicClient` del SDK (cacheado por proceso en `core.polymarket_client`).

  list_events(...)  -> eventos crudos del SDK (para leer sus markets, ej. goles).
  match_events(...) -> eventos de PARTIDO ('X vs Y') normalizados: equipos + kickoff.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from core.polymarket_client import build_public_client
from venue.matching import canon

WORLD_CUP_TAG_ID = 102232

_VS = re.compile(r"^(.+?)\s+vs\.?\s+(.+?)\??$", re.I)
_WILL_WIN = re.compile(r"\s*will\s+(.+?)\s+win\b", re.I)


def list_events(tag_id: int = WORLD_CUP_TAG_ID, *, closed: bool = False,
                limit: int = 1400) -> list:
    """Eventos de Polymarket para un tag, vía el PublicClient del SDK (read-only)."""
    out: list = []
    for page in build_public_client().list_events(tag_ids=tag_id, closed=closed, page_size=100):
        out.extend(page.items)
        if len(out) >= limit:
            break
    return out


def kickoff_of(ev) -> datetime | None:
    """Hora de inicio del partido: event.schedule.start_time (o None)."""
    sch = getattr(ev, "schedule", None)
    return getattr(sch, "start_time", None) if sch is not None else None


@dataclass(frozen=True)
class MatchEvent:
    title: str
    home_disp: str
    away_disp: str
    home_canon: str
    away_canon: str
    kickoff: datetime | None
    has_winner_market: bool
    event: object  # evento crudo del SDK (para leer sus markets)


def match_events(tag_id: int = WORLD_CUP_TAG_ID, *, closed: bool = False,
                 limit: int = 1400) -> list[MatchEvent]:
    """Eventos de PARTIDO ('X vs Y') normalizados: nombres canónicos + kickoff.

    Salta los que no son partido (novelty, futuros) o sin mercado 'Will X win'.
    """
    out: list[MatchEvent] = []
    for ev in list_events(tag_id, closed=closed, limit=limit):
        title = (getattr(ev, "title", "") or "").split(" - ")[0]
        m = _VS.match(title)
        if not m:
            continue
        markets = getattr(ev, "markets", None) or []
        has_win = any(_WILL_WIN.match(getattr(mk, "question", "") or "") for mk in markets)
        out.append(MatchEvent(
            title=title,
            home_disp=m.group(1).strip(), away_disp=m.group(2).strip(),
            home_canon=canon(m.group(1)), away_canon=canon(m.group(2)),
            kickoff=kickoff_of(ev), has_winner_market=has_win, event=ev,
        ))
    return out
