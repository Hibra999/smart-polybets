#!/usr/bin/env python
"""Ingesta de MINUTOS DE GOL (y rojas) de Liga MX desde el scoreboard de ESPN.

Para modelar las reglas del theta trade necesitamos el timing de los goles
(hazard por minuto, supervivencia del 0-0, cuándo anota el favorito), que
football-data NO trae. Fuente: API pública JSON de ESPN (`mex.1`), sin key —
fuente deportiva externa permitida (misma categoría que football-data; la regla
anti-scraper es solo para Polymarket).

Crawl diario del rango de temporada → tabla `match_timeline_event` en el SQLite
del torneo: goles (con minuto y lado) + tarjetas rojas (mueven el precio igual
que un gol). IDEMPOTENTE: borra el source y reinserta.

    python data/liga_mx_2026/ingest/fetch_goal_minutes_espn.py            # 2025/26
    python data/liga_mx_2026/ingest/fetch_goal_minutes_espn.py --from 2024-07-01 --to 2025-06-30
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
import unicodedata
import urllib.request
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.console import enable_utf8

enable_utf8()

TID = "liga_mx_2026"
DB = REPO_ROOT / "data" / TID / f"{TID}.sqlite"
URL = "https://site.api.espn.com/apis/site/v2/sports/soccer/mex.1/scoreboard?dates={d}"
SOURCE = "espn"

DDL = """
CREATE TABLE IF NOT EXISTS match_timeline_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    espn_event_id TEXT,
    match_date TEXT NOT NULL,
    home_team_id TEXT, away_team_id TEXT,
    home_raw TEXT, away_raw TEXT,
    side TEXT,                -- 'home' | 'away'
    event_type TEXT,          -- 'goal' | 'own_goal' | 'penalty_goal' | 'red_card'
    minute REAL,              -- minuto de juego (45+2 -> 45 + 2/10 NO: se guarda base+extra aparte)
    minute_base INTEGER,      -- minuto mostrado (45 en '45+2')
    minute_extra INTEGER,     -- añadido (2 en '45+2'; 0 si no hay)
    clock_seconds REAL,       -- clock.value de ESPN (segundos de juego)
    display TEXT,
    home_score_final INTEGER, away_score_final INTEGER
);
CREATE INDEX IF NOT EXISTS idx_timeline_date ON match_timeline_event(match_date);
"""

# nombre ESPN (canon sin acentos, lower) -> team_id del proyecto
ESPN_MAP = {
    "america": "america", "club america": "america",
    "guadalajara": "guadalajara", "chivas": "guadalajara",
    "cruz azul": "cruz_azul",
    "pumas unam": "pumas_unam", "unam": "pumas_unam", "pumas": "pumas_unam",
    "tigres uanl": "tigres_uanl", "uanl": "tigres_uanl", "tigres": "tigres_uanl",
    "monterrey": "monterrey",
    "toluca": "toluca", "deportivo toluca": "toluca",
    "pachuca": "pachuca",
    "leon": "leon", "club leon": "leon",
    "atlas": "atlas",
    "santos laguna": "santos_laguna", "santos": "santos_laguna",
    "juarez": "juarez", "fc juarez": "juarez",
    "queretaro": "queretaro",
    "atletico de san luis": "atletico_san_luis", "atletico san luis": "atletico_san_luis",
    "san luis": "atletico_san_luis",
    "mazatlan": "mazatlan", "mazatlan fc": "mazatlan",
    "tijuana": "tijuana", "club tijuana": "tijuana", "xolos": "tijuana",
    "puebla": "puebla",
    "necaxa": "necaxa",
    "atlante": "atlante",
}

GOAL_TYPES = {"70": "goal", "137": "own_goal", "98": "penalty_goal", "173": "penalty_goal"}
RED_TYPES = {"93": "red_card", "134": "red_card"}  # roja directa / segunda amarilla


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s).strip()


def map_team(name: str) -> str | None:
    return ESPN_MAP.get(norm(name))


def parse_minute(display: str) -> tuple[int, int]:
    m = re.match(r"(\d+)'(?:\s*\+\s*(\d+)')?", display or "")
    if not m:
        return 0, 0
    return int(m.group(1)), int(m.group(2) or 0)


def fetch_day(d: date) -> list[dict]:
    url = URL.format(d=d.strftime("%Y%m%d"))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read()).get("events", [])


def run(dfrom: date, dto: date, apply: bool) -> None:
    con = sqlite3.connect(DB)
    con.executescript(DDL)
    rows: list[tuple] = []
    seen_events: set[str] = set()
    unmapped: set[str] = set()
    days = (dto - dfrom).days + 1
    print(f"=== ESPN goal minutes: {dfrom} → {dto} ({days} días) ===")
    d = dfrom
    n_matches = 0
    while d <= dto:
        try:
            events = fetch_day(d)
        except Exception as exc:  # noqa: BLE001 — un día caído no mata el crawl
            print(f"  [warn] {d}: {exc}")
            events = []
        for e in events:
            eid = str(e.get("id"))
            if eid in seen_events:
                continue
            seen_events.add(eid)
            comp = (e.get("competitions") or [{}])[0]
            if (comp.get("status") or {}).get("type", {}).get("completed") is not True:
                continue
            comps = comp.get("competitors") or []
            home = next((c for c in comps if c.get("homeAway") == "home"), None)
            away = next((c for c in comps if c.get("homeAway") == "away"), None)
            if not home or not away:
                continue
            hname = (home.get("team") or {}).get("displayName") or ""
            aname = (away.get("team") or {}).get("displayName") or ""
            hid_espn = str((home.get("team") or {}).get("id"))
            hmap, amap = map_team(hname), map_team(aname)
            if hmap is None:
                unmapped.add(hname)
            if amap is None:
                unmapped.add(aname)
            hs = int(home.get("score") or 0)
            as_ = int(away.get("score") or 0)
            n_matches += 1
            for det in comp.get("details") or []:
                tid_evt = str((det.get("type") or {}).get("id"))
                etype = GOAL_TYPES.get(tid_evt) or RED_TYPES.get(tid_evt)
                if etype is None and det.get("scoringPlay"):
                    etype = "goal"
                if etype is None:
                    continue
                side = "home" if str((det.get("team") or {}).get("id")) == hid_espn else "away"
                if etype == "own_goal":  # el gol lo RECIBE el equipo del autogolero
                    side = "away" if side == "home" else "home"
                disp = (det.get("clock") or {}).get("displayValue") or ""
                base, extra = parse_minute(disp)
                rows.append((SOURCE, eid, str(e.get("date"))[:10], hmap, amap,
                             hname, aname, side, etype,
                             base + extra, base, extra,
                             (det.get("clock") or {}).get("value"), disp, hs, as_))
        time.sleep(0.15)
        d += timedelta(days=1)

    goals = sum(1 for r in rows if r[8] != "red_card")
    reds = sum(1 for r in rows if r[8] == "red_card")
    print(f"\npartidos completados: {n_matches} · goles: {goals} · rojas: {reds}")
    if unmapped:
        print(f"[WARN] equipos ESPN sin mapear: {sorted(unmapped)}")
    if apply:
        con.execute("DELETE FROM match_timeline_event WHERE source=? AND match_date BETWEEN ? AND ?",
                    (SOURCE, dfrom.isoformat(), dto.isoformat()))
        con.executemany(
            "INSERT INTO match_timeline_event(source, espn_event_id, match_date, home_team_id, "
            "away_team_id, home_raw, away_raw, side, event_type, minute, minute_base, "
            "minute_extra, clock_seconds, display, home_score_final, away_score_final) "
            f"VALUES({','.join('?'*16)})", rows)
        con.commit()
        print(f"[APLICADO] {len(rows)} eventos de timeline")
    else:
        print("[DRY-RUN] usar --apply para escribir")
    con.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default="2025-07-01")
    ap.add_argument("--to", dest="dto", default="2026-05-31")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    run(date.fromisoformat(a.dfrom), date.fromisoformat(a.dto), a.apply)


if __name__ == "__main__":
    main()
