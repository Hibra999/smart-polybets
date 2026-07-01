#!/usr/bin/env python
"""Migra los datos del Mundial 2026 desde pypro_worldcup_betting al SQLite del agente.

Lee `worldcup.db` (tournament kind='live', WC 2026) y puebla
`data/fifa_world_cup_2026/fifa_world_cup_2026.sqlite` con el schema canónico
`football.sql`:
  - tournament  ← edición 2026
  - team        ← nombre + elo_rating (= elo_seed del origen)
  - phase       ← etapas distintas (group/R16/QF/SF/3rd/final) con is_knockout
  - fixture     ← partidos (goles/status), kickoff derivado de date+id (orden estable)

No migra cuotas (el schema del agente no las modela; las cuotas viven en Polymarket
vía research/market_scanner). Idempotente: reconstruye la DB destino desde cero.

Uso:
    python scripts/migrate_worldcup_data.py \
        --source "C:/0_documentos/gits/pypro/pypro_worldcup_betting/app/data/worldcup.db"
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FOOTBALL_DDL = REPO_ROOT / "data" / "_schema" / "football.sql"
DEFAULT_SOURCE = (
    REPO_ROOT.parent / "pypro_worldcup_betting" / "app" / "data" / "worldcup.db"
)
TARGET_ID = "fifa_world_cup_2026"

# stage del origen → (phase_id, phase_name, order, is_knockout)
_STAGE_MAP = {
    "group": ("group_stage", "Group Stage", 1, 0),
    "R16": ("r16", "Round of 16", 2, 1),
    "QF": ("qf", "Quarter-finals", 3, 1),
    "SF": ("sf", "Semi-finals", 4, 1),
    "3rd": ("third_place", "Third place", 5, 1),
    "final": ("final", "Final", 6, 1),
}
_STATUS_FINISHED = ("STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_FT")

# Puntos FIFA (ranking 11-jun-2026) de las selecciones del Mundial 2026 que NO
# están en el snapshot de 40 equipos de worldcup. Las claves usan el nombre
# canónico ESPN (igual que worldcup.db). Fuente: ESPN + whereig.com.
# Se convierten a Elo con el MISMO mapeo lineal que los 40 ya sembrados (ajustado
# empíricamente desde worldcup), para mantener la escala consistente.
_SUPPLEMENT_FIFA = {
    "Türkiye": 1605.73, "Algeria": 1571.03, "Ivory Coast": 1540.87, "Czechia": 1505.74,
    "Paraguay": 1505.35, "Scotland": 1503.34, "Tunisia": 1476.41, "Congo DR": 1474.43,
    "Uzbekistan": 1458.73, "Iraq": 1446.28, "South Africa": 1428.38, "Jordan": 1387.74,
    "Bosnia-Herzegovina": 1387.22, "Cape Verde": 1371.11, "Curaçao": 1294.77,
    "Haiti": 1293.10, "New Zealand": 1275.58,
}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _fit_fifa_to_elo(teams: dict) -> tuple[float, float]:
    """Ajusta (slope, intercept) de elo = intercept + slope·fifa desde los pares
    (fifa_points, elo_seed) ya almacenados en worldcup (relación exactamente lineal).
    Devuelve (0.9, ·) por defecto si no hay datos suficientes."""
    pts = [(t["fifa_points"], t["elo_seed"]) for t in teams.values()
           if t.get("fifa_points") is not None and t.get("elo_seed") is not None]
    if len(pts) < 2:
        return 0.9, 1500.0 - 0.9 * 1623.7  # fallback al anchor conocido
    pts.sort()
    (f1, e1), (f2, e2) = pts[0], pts[-1]
    slope = (e2 - e1) / (f2 - f1)
    intercept = e1 - slope * f1
    return slope, intercept


def _kickoff(date: str, ordinal: int) -> str:
    """ISO kickoff realista: los partidos del día arrancan desde 13:00 UTC, en
    slots de 30 min según su orden en la jornada (`ordinal`).

    worldcup.db sólo guarda la fecha (sin hora); asignamos horarios de tarde/noche
    (los reales del Mundial) para que la ventana temporal del agente tenga sentido
    y el orden cronológico dentro del día sea estable.
    """
    total_min = 13 * 60 + ordinal * 30
    return f"{date}T{total_min // 60:02d}:{total_min % 60:02d}:00+00:00"


def migrate(source: Path, target: Path) -> dict:
    if not source.exists():
        raise FileNotFoundError(f"worldcup.db no encontrado: {source}")

    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row

    wc = src.execute(
        "SELECT * FROM tournament WHERE kind='live' ORDER BY year DESC"
    ).fetchone()
    if wc is None:
        raise RuntimeError("No hay torneo 'live' en worldcup.db")
    wc_tid = wc["id"]

    teams = {t["id"]: dict(t) for t in src.execute("SELECT * FROM team")}
    matches = [
        dict(m)
        for m in src.execute(
            "SELECT * FROM match WHERE tournament_id=? ORDER BY date, id", (wc_tid,)
        )
    ]

    # equipos que aparecen en el calendario 2026
    used_team_ids = {m["home_team_id"] for m in matches} | {
        m["away_team_id"] for m in matches
    }

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    dst = sqlite3.connect(target)
    dst.executescript(FOOTBALL_DDL.read_text(encoding="utf-8"))

    dates = [m["date"] for m in matches if m["date"]]
    dst.execute(
        "INSERT INTO tournament(id,name,sport,format,start_date,end_date,n_teams,source_url) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (TARGET_ID, "FIFA World Cup 2026", "football", "world_cup",
         min(dates) if dates else "2026-06-11", max(dates) if dates else None,
         len(used_team_ids), "migrated:pypro_worldcup_betting"),
    )

    # phases
    for phase_id, name, order, knockout in _STAGE_MAP.values():
        dst.execute(
            "INSERT OR IGNORE INTO phase(id,tournament_id,name,phase_order,is_knockout) "
            "VALUES(?,?,?,?,?)",
            (phase_id, TARGET_ID, name, order, knockout),
        )

    # teams (id agente = slug del nombre)
    slope, intercept = _fit_fifa_to_elo(teams)
    id_map: dict[int, str] = {}
    n_supplemented = 0
    for wc_team_id in used_team_ids:
        t = teams.get(wc_team_id)
        if not t:
            continue
        agent_id = slug(t["name"])
        id_map[wc_team_id] = agent_id
        elo = t["elo_seed"]
        # Equipos sin semilla en worldcup pero con puntos FIFA conocidos → sembrar.
        if elo is None and t["name"] in _SUPPLEMENT_FIFA:
            elo = round(intercept + slope * _SUPPLEMENT_FIFA[t["name"]], 2)
            n_supplemented += 1
        dst.execute(
            "INSERT OR IGNORE INTO team(id,tournament_id,name,short_name,elo_rating) "
            "VALUES(?,?,?,?,?)",
            (agent_id, TARGET_ID, t["name"], t["name"][:3].upper(), elo),
        )

    # fixtures
    n_finished = 0
    pair_to_fixture: dict[tuple[str, str], str] = {}
    day_ordinal: dict[str, int] = {}
    for m in matches:
        home = id_map.get(m["home_team_id"])
        away = id_map.get(m["away_team_id"])
        if not home or not away:
            continue
        phase_id = _STAGE_MAP.get(m["stage"], _STAGE_MAP["group"])[0]
        finished = m["status"] in _STATUS_FINISHED and m["home_goals"] is not None
        status = "finished" if finished else "scheduled"
        winner = None
        if finished:
            n_finished += 1
            if m["home_goals"] > m["away_goals"]:
                winner = home
            elif m["away_goals"] > m["home_goals"]:
                winner = away
        fixture_id = f"wc_{m['id']}"
        pair_to_fixture[(home, away)] = fixture_id
        ordinal = day_ordinal.get(m["date"], 0)
        day_ordinal[m["date"]] = ordinal + 1
        dst.execute(
            "INSERT INTO fixture(id,tournament_id,phase_id,home_team_id,away_team_id,"
            "kickoff_utc,status,home_goals,away_goals,winner_team_id,neutral_venue) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,1)",
            (fixture_id, TARGET_ID, phase_id, home, away,
             _kickoff(m["date"], ordinal), status,
             m["home_goals"] if finished else None,
             m["away_goals"] if finished else None, winner),
        )

    # cuotas (Polymarket + Codere) → tabla auxiliar `polymarket_odds`
    # (fuera del schema football.sql canónico: representan datos de mercado, no
    # del deporte). El market_source las lee para alimentar research/.
    dst.executescript(
        """
        CREATE TABLE polymarket_odds (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id    TEXT,
            source        TEXT,
            home_team_id  TEXT,
            away_team_id  TEXT,
            home_decimal  REAL, away_decimal REAL, draw_decimal REAL,
            home_prob     REAL, away_prob REAL,
            fetched_at    TEXT
        );
        CREATE INDEX ix_odds_fixture ON polymarket_odds(fixture_id, source);
        """
    )
    n_odds = 0
    for o in src.execute("SELECT * FROM odds WHERE tournament_id=?", (wc_tid,)):
        o = dict(o)
        home = id_map.get(o["home_team_id"])
        away = id_map.get(o["away_team_id"])
        fixture_id = pair_to_fixture.get((home, away))
        if not fixture_id:
            continue
        dst.execute(
            "INSERT INTO polymarket_odds(fixture_id,source,home_team_id,away_team_id,"
            "home_decimal,away_decimal,draw_decimal,home_prob,away_prob,fetched_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (fixture_id, o["source"], home, away, o["home_decimal"], o["away_decimal"],
             o["draw_decimal"], o["home_prob"], o["away_prob"], o["fetched_at"]),
        )
        n_odds += 1

    dst.commit()
    dst.close()
    src.close()
    return {
        "teams": len(id_map),
        "teams_supplemented_fifa": n_supplemented,
        "fixtures": len(matches),
        "finished": n_finished,
        "scheduled": len(matches) - n_finished,
        "odds": n_odds,
        "target": str(target),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Migra worldcup.db → SQLite del agente.")
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument(
        "--target",
        type=Path,
        default=REPO_ROOT / "data" / TARGET_ID / f"{TARGET_ID}.sqlite",
    )
    args = ap.parse_args()
    stats = migrate(args.source, args.target)
    print("[OK] Migracion completa:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
