"""Ingesta de métricas por equipo desde play-by-play oficial de nflverse."""
from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DB = REPO_ROOT / "data" / "nfl_2026" / "nfl_2026.sqlite"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{year}.csv"
USECOLS = [
    "game_id", "home_team", "away_team", "posteam", "epa", "success",
    "yards_gained", "pass_attempt", "rush_attempt", "pass_oe",
]


def aggregate_team_stats(pbp: pd.DataFrame) -> list[dict]:
    """Agrega sólo información observable al finalizar cada juego."""
    records = []
    for game_id, game in pbp.groupby("game_id", sort=False):
        teams = (str(game["home_team"].iloc[0]), str(game["away_team"].iloc[0]))
        for team in teams:
            offense = game[(game["posteam"] == team) & game["epa"].notna()]
            defense = game[(game["posteam"].notna()) & (game["posteam"] != team)
                           & game["epa"].notna()]
            attempts = offense["pass_attempt"].fillna(0).sum() + offense[
                "rush_attempt"].fillna(0).sum()
            records.append({
                "fixture_id": str(game_id),
                "team_id": team,
                "plays": len(offense),
                "offensive_epa_per_play": _mean(offense["epa"]),
                "defensive_epa_per_play": _negative_mean(defense["epa"]),
                "success_rate": _mean(offense["success"]),
                "explosive_play_rate": _mean(offense["yards_gained"] >= 20),
                "pass_rate": float(offense["pass_attempt"].fillna(0).sum() / attempts)
                if attempts else None,
                "proe": _mean(offense["pass_oe"]),
            })
    return records


def _mean(series: pd.Series) -> float | None:
    clean = series.dropna()
    return float(clean.mean()) if not clean.empty else None


def _negative_mean(series: pd.Series) -> float | None:
    value = _mean(series)
    return -value if value is not None else None


def upsert_team_stats(
    db: Path,
    records: list[dict],
    unavailable_years: tuple[int, ...] = (),
    *,
    log_ingest: bool = True,
) -> int:
    connection = sqlite3.connect(db)
    valid = {
        row[0] for row in connection.execute(
            "SELECT id FROM fixture WHERE status='finished'")
    }
    rows = [row for row in records if row["fixture_id"] in valid]
    columns = (
        "fixture_id", "team_id", "plays", "offensive_epa_per_play",
        "defensive_epa_per_play", "success_rate", "explosive_play_rate", "pass_rate", "proe",
    )
    connection.executemany(
        f"INSERT INTO match_team_stat({','.join(columns)}) "
        f"VALUES({','.join('?' for _ in columns)}) ON CONFLICT(fixture_id,team_id) DO UPDATE SET "
        + ",".join(f"{column}=excluded.{column}" for column in columns[2:]),
        [tuple(row[column] for column in columns) for row in rows],
    )
    if log_ingest:
        _log_ingest(connection, len(rows), unavailable_years)
    connection.commit()
    connection.close()
    return len(rows)


def _log_ingest(
    connection: sqlite3.Connection, records: int, unavailable_years: tuple[int, ...]
) -> None:
    status = "partial" if unavailable_years else "ok"
    note = (
        f"play-by-play no publicado: {', '.join(map(str, unavailable_years))}"
        if unavailable_years
        else None
    )
    connection.execute(
        "INSERT INTO ingest_log(tournament_id,source,entity_type,records_inserted,status,error_msg) "
        "VALUES('nfl_2026','nflverse-pbp','match_team_stat',?,?,?)",
        (records, status, note),
    )


def load_pbp(year: int) -> pd.DataFrame | None:
    """Carga un solo año; None significa que el año actual aún no fue publicado."""
    current_year = datetime.now(UTC).year
    try:
        return pd.read_csv(PBP_URL.format(year=year), usecols=USECOLS, low_memory=False)
    except HTTPError as error:
        if error.code != 404 or year < current_year:
            raise
        return None


def run(db: Path, since: int, through: int) -> int:
    total = 0
    unavailable: list[int] = []
    for year in range(since, through + 1):
        pbp = load_pbp(year)
        if pbp is None:
            unavailable.append(year)
            continue
        total += upsert_team_stats(db, aggregate_team_stats(pbp), log_ingest=False)
    if total == 0:
        raise RuntimeError("nflverse no publicó ningún año solicitado de play-by-play")
    connection = sqlite3.connect(db)
    _log_ingest(connection, total, tuple(unavailable))
    connection.commit()
    connection.close()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--since", type=int, default=2010)
    parser.add_argument("--through", type=int, default=2026)
    args = parser.parse_args()
    print(f"match_team_stat: {run(args.db, args.since, args.through)}")


if __name__ == "__main__":
    main()
