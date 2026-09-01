"""Ingesta de roster semanal y depth chart de nflverse."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DB = REPO_ROOT / "data" / "nfl_2026" / "nfl_2026.sqlite"
ROSTER_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/"
    "roster_weekly_{season}.csv"
)
DEPTH_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/depth_charts/"
    "depth_charts_{season}.csv"
)


def player_records(roster: pd.DataFrame, depth: pd.DataFrame) -> list[dict]:
    latest = roster.dropna(subset=["gsis_id", "team"]).sort_values("week").drop_duplicates(
        "gsis_id", keep="last")
    ranks: dict[str, int] = {}
    if not depth.empty and {"gsis_id", "pos_rank"}.issubset(depth.columns):
        recent = depth.dropna(subset=["gsis_id"]).sort_values("dt").drop_duplicates(
            "gsis_id", keep="last")
        ranks = {str(row.gsis_id): int(row.pos_rank) for row in recent.itertuples()
                 if pd.notna(row.pos_rank)}
    records = []
    for row in latest.itertuples():
        player_id = str(row.gsis_id)
        records.append({
            "id": player_id,
            "team_id": str(row.team),
            "name": str(row.full_name),
            "position": str(row.position),
            "jersey_number": _integer(getattr(row, "jersey_number", None)),
            "depth_chart_rank": ranks.get(player_id),
            "years_exp": _integer(getattr(row, "years_exp", None)),
            "status": _status(str(getattr(row, "status", "active"))),
        })
    return records


def _integer(value) -> int | None:
    return int(value) if pd.notna(value) else None


def _status(value: str) -> str:
    return {"ACT": "active", "RES": "injured_ir", "SUS": "suspended",
            "DEV": "practice_squad"}.get(value.upper(), value.lower())


def upsert_players(db: Path, records: list[dict], *, injury_available: bool = False) -> int:
    connection = sqlite3.connect(db)
    teams = {row[0] for row in connection.execute("SELECT id FROM team")}
    rows = [row for row in records if row["team_id"] in teams]
    columns = (
        "id", "tournament_id", "team_id", "name", "position", "jersey_number",
        "depth_chart_rank", "years_exp", "status",
    )
    values = [
        (row["id"], "nfl_2026", row["team_id"], row["name"], row["position"],
         row["jersey_number"], row["depth_chart_rank"], row["years_exp"], row["status"])
        for row in rows
    ]
    connection.executemany(
        f"INSERT INTO player({','.join(columns)}) VALUES({','.join('?' for _ in columns)}) "
        "ON CONFLICT(id) DO UPDATE SET team_id=excluded.team_id,name=excluded.name,"
        "position=excluded.position,jersey_number=excluded.jersey_number,"
        "depth_chart_rank=excluded.depth_chart_rank,years_exp=excluded.years_exp,"
        "status=excluded.status",
        values,
    )
    status = "ok" if injury_available else "partial"
    note = None if injury_available else "nflverse no publica injury report 2026; no se imputó"
    connection.execute(
        "INSERT INTO ingest_log(tournament_id,source,entity_type,records_inserted,status,error_msg) "
        "VALUES('nfl_2026','nflverse','player/injury_report',?,?,?)",
        (len(rows), status, note),
    )
    connection.commit()
    connection.close()
    return len(rows)


def run(db: Path, season: int) -> int:
    roster = pd.read_csv(ROSTER_URL.format(season=season), low_memory=False)
    depth = pd.read_csv(DEPTH_URL.format(season=season), low_memory=False)
    return upsert_players(db, player_records(roster, depth))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()
    print(f"players: {run(args.db, args.season)} (injury_report: unavailable/partial)")


if __name__ == "__main__":
    main()
