#!/usr/bin/env python
"""Migra datos NFL (nflverse) al SQLite del agente para la temporada 2026.

Toma `games.csv` de nflverse (todas las temporadas con resultados + el calendario
2026) y puebla `data/nfl_2026/nfl_2026.sqlite` con el schema `american_football.sql`:
  - tournament (nfl_2026)
  - team       (32 franquicias)
  - week       (por season/week/game_type)
  - fixture    (2010-2026: histórico finished + 2026 scheduled)

El histórico ampliado sirve para investigación. La estrategia TrueSkill activa sigue
anclada a 2022; los juegos 2026 son los fixtures programados que el adapter predice.

    python scripts/migrate_nfl_data.py [--since 2010]
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
FOOTBALL_DDL = REPO_ROOT / "data" / "_schema" / "american_football.sql"
GAMES_URL = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
TARGET_ID = "nfl_2026"
SEASON = 2026

# Código nflverse → apodo de la franquicia.
TEAM_NAMES = {
    "ARI": "Cardinals", "ATL": "Falcons", "BAL": "Ravens", "BUF": "Bills",
    "CAR": "Panthers", "CHI": "Bears", "CIN": "Bengals", "CLE": "Browns",
    "DAL": "Cowboys", "DEN": "Broncos", "DET": "Lions", "GB": "Packers",
    "HOU": "Texans", "IND": "Colts", "JAX": "Jaguars", "KC": "Chiefs",
    "LV": "Raiders", "LAC": "Chargers", "LAR": "Rams", "LA": "Rams",
    "MIA": "Dolphins", "MIN": "Vikings", "NE": "Patriots", "NO": "Saints",
    "NYG": "Giants", "NYJ": "Jets", "PHI": "Eagles", "PIT": "Steelers",
    "SF": "49ers", "SEA": "Seahawks", "TB": "Buccaneers", "TEN": "Titans",
    "WAS": "Commanders", "OAK": "Raiders", "SD": "Chargers", "STL": "Rams",
}
_PHASE = {"REG": "regular", "WC": "wildcard", "DIV": "divisional",
          "CON": "conference", "SB": "superbowl", "POST": "playoff"}


def _kickoff(row) -> str:
    day = str(row.get("gameday") or f"{int(row['season'])}-09-01")
    t = str(row.get("gametime") or "")
    if t and ":" in t:
        local = datetime.fromisoformat(f"{day}T{t}:00").replace(
            tzinfo=ZoneInfo("America/New_York")
        )
        return local.astimezone(UTC).isoformat()
    return f"{day}T17:00:00+00:00"


def migrate(target: Path, since: int) -> dict:
    df = pd.read_csv(GAMES_URL)
    df = df[df["season"] >= since].copy()
    df = df.sort_values(["gameday", "season", "week"]).reset_index(drop=True)

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    dst = sqlite3.connect(target)
    dst.executescript(FOOTBALL_DDL.read_text(encoding="utf-8"))

    dst.execute(
        "INSERT INTO tournament(id,name,sport,season_year,start_date,end_date) "
        "VALUES(?,?,?,?,?,?)",
        (TARGET_ID, "NFL 2026 Season", "american_football", SEASON,
         "2026-09-06", "2027-02-08"),
    )

    teams = set(df["home_team"]) | set(df["away_team"])
    for code in sorted(teams):
        dst.execute(
            "INSERT OR IGNORE INTO team(id,tournament_id,name) VALUES(?,?,?)",
            (code, TARGET_ID, TEAM_NAMES.get(code, code)),
        )

    weeks: dict[str, tuple] = {}
    for _, r in df.iterrows():
        gt = str(r.get("game_type") or "REG")
        wid = f"{int(r['season'])}_{gt}_w{int(r['week'])}"
        if wid not in weeks:
            weeks[wid] = (wid, TARGET_ID, int(r["week"]), _PHASE.get(gt, "regular"))
    for w in weeks.values():
        dst.execute(
            "INSERT OR IGNORE INTO week(id,tournament_id,week_number,phase) VALUES(?,?,?,?)", w
        )

    n_finished = n_sched = 0
    for _, r in df.iterrows():
        gid = str(r.get("game_id") or f"{int(r['season'])}_{int(r['week']):02d}_{r['away_team']}_{r['home_team']}")
        home, away = r["home_team"], r["away_team"]
        gt = str(r.get("game_type") or "REG")
        wid = f"{int(r['season'])}_{gt}_w{int(r['week'])}"
        hs, as_ = r.get("home_score"), r.get("away_score")
        finished = pd.notna(hs) and pd.notna(as_)
        status = "finished" if finished else "scheduled"
        winner = None
        if finished:
            n_finished += 1
            if hs > as_:
                winner = home
            elif as_ > hs:
                winner = away
        else:
            n_sched += 1
        dst.execute(
            "INSERT INTO fixture(id,tournament_id,week_id,home_team_id,away_team_id,"
            "kickoff_utc,status,home_score,away_score,winner_team_id,went_to_ot,"
            "spread_home,total_ou,moneyline_home,moneyline_away) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (gid, TARGET_ID, wid, home, away, _kickoff(r), status,
             int(hs) if finished else None, int(as_) if finished else None, winner,
             1 if (pd.notna(r.get("overtime")) and r.get("overtime")) else 0,
             r.get("spread_line") if pd.notna(r.get("spread_line")) else None,
             r.get("total_line") if pd.notna(r.get("total_line")) else None,
             int(r["home_moneyline"]) if pd.notna(r.get("home_moneyline")) else None,
             int(r["away_moneyline"]) if pd.notna(r.get("away_moneyline")) else None),
        )

    dst.commit()
    dst.close()
    return {"teams": len(teams), "weeks": len(weeks), "finished": n_finished,
            "scheduled": n_sched, "seasons": f"{since}-{int(df['season'].max())}",
            "target": str(target)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=2010)
    ap.add_argument("--target", type=Path,
                    default=REPO_ROOT / "data" / TARGET_ID / f"{TARGET_ID}.sqlite")
    a = ap.parse_args()
    stats = migrate(a.target, a.since)
    print("[OK] Migracion NFL completa:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
