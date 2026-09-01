#!/usr/bin/env python
"""Ingesta de Liga MX Apertura 2026 desde Polymarket (SDK vía venue/discovery).

Puebla/actualiza el SQLite del torneo con:
  - tournament + phases (regular / liguilla)
  - los 18 equipos (ids canónicos; elo seed flat 1500 — cold start documentado)
  - fixtures de los partidos listados en Polymarket (tag Liga MX = 102448)

Polymarket lista los partidos en ventana rodante (~2 jornadas hacia adelante):
correr a DIARIO durante la temporada (un mercado
que cierra entre corridas deja el fixture huérfano, ver finding 2026-07-09).

IDEMPOTENTE: equipos por PK; fixtures matcheados por (home, away, fecha) — re-run
no duplica, y si el kickoff se movió lo actualiza.

    python data/liga_mx_2026/ingest/fetch_fixtures_pm.py            # dry-run
    python data/liga_mx_2026/ingest/fetch_fixtures_pm.py --apply    # escribe
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from core.console import enable_utf8

enable_utf8()

from tournaments.registry import get_config
from venue.discovery import match_events
from venue.matching import canon

TID = "liga_mx_2026"
LIGA_MX_TAG_ID = 102448
DB = REPO_ROOT / "data" / TID / f"{TID}.sqlite"

# id canónico → (nombre display, short, aliases como aparecen en Polymarket)
TEAMS: dict[str, tuple[str, str, list[str]]] = {
    "america":           ("América", "AME", ["CF América", "América", "Club America"]),
    "guadalajara":       ("Guadalajara", "GDL", ["CD Guadalajara", "Guadalajara", "Chivas"]),
    "cruz_azul":         ("Cruz Azul", "CAZ", ["CF Cruz Azul", "Cruz Azul"]),
    "pumas_unam":        ("Pumas UNAM", "PUM", ["Pumas de la UNAM", "Pumas UNAM"]),
    "tigres_uanl":       ("Tigres UANL", "TIG", ["Tigres de la UANL", "Tigres UANL"]),
    "monterrey":         ("Monterrey", "MTY", ["CF Monterrey", "Monterrey"]),
    "toluca":            ("Toluca", "TOL", ["Deportivo Toluca FC", "Toluca"]),
    "pachuca":           ("Pachuca", "PAC", ["CF Pachuca", "Pachuca"]),
    "leon":              ("León", "LEO", ["Club León FC", "León", "Club Leon"]),
    "atlas":             ("Atlas", "ATS", ["Atlas FC", "Atlas"]),
    "santos_laguna":     ("Santos Laguna", "SAN", ["Club Santos Laguna", "Santos Laguna"]),
    "juarez":            ("Juárez", "JUA", ["FC Juárez", "Juárez", "FC Juarez"]),
    "queretaro":         ("Querétaro", "QRO", ["Querétaro FC", "Querétaro", "Queretaro"]),
    "atletico_san_luis": ("Atlético San Luis", "ASL", ["Atlético San Luis", "Atlético de San Luis"]),
    "atlante":           ("Atlante", "ATL", ["Atlante FC", "Atlante"]),
    "tijuana":           ("Tijuana", "TIJ", ["Club Tijuana", "Tijuana", "Xolos"]),
    "puebla":            ("Puebla", "PUE", ["Club Puebla", "Puebla"]),
    "necaxa":            ("Necaxa", "NEC", ["Club Necaxa", "Necaxa"]),
}

ALIAS_TO_ID: dict[str, str] = {}
for tid_, (_, _, aliases) in TEAMS.items():
    for a in aliases:
        ALIAS_TO_ID[canon(a)] = tid_

SEED_ELO = 1500.0  # cold start (flat); ver TOURNAMENT.md — pendiente seed Clausura 2026


def ensure_base_rows(con: sqlite3.Connection) -> None:
    con.execute(
        "INSERT OR IGNORE INTO tournament(id, name, sport, format, start_date) "
        "VALUES(?, 'Liga MX Apertura 2026', 'football', 'league', '2026-07-16')", (TID,))
    con.execute(
        "INSERT OR IGNORE INTO phase(id, tournament_id, name, phase_order, is_knockout) "
        "VALUES('regular', ?, 'Fase regular', 1, 0)", (TID,))
    con.execute(
        "INSERT OR IGNORE INTO phase(id, tournament_id, name, phase_order, is_knockout) "
        "VALUES('liguilla', ?, 'Liguilla', 2, 1)", (TID,))
    for tid_, (name, short, _) in TEAMS.items():
        con.execute(
            "INSERT OR IGNORE INTO team(id, tournament_id, name, short_name, "
            "country_code, elo_rating) VALUES(?, ?, ?, ?, 'MEX', ?)",
            (tid_, TID, name, short, SEED_ELO))


def discover_matches(*, include_closed: bool = False) -> list[tuple[str, str, str]]:
    """Partidos únicos del Apertura; al mezclar estados, el mercado abierto gana."""
    cfg = get_config(TID)
    seen: dict[tuple[str, str, str], tuple[str, str, str]] = {}
    unknown: set[str] = set()
    for closed in ((True, False) if include_closed else (False,)):
        for me in match_events(tag_id=LIGA_MX_TAG_ID, closed=closed):
            if not me.has_winner_market or me.kickoff is None:
                continue
            h = ALIAS_TO_ID.get(me.home_canon) or ALIAS_TO_ID.get(canon(me.home_disp))
            a = ALIAS_TO_ID.get(me.away_canon) or ALIAS_TO_ID.get(canon(me.away_disp))
            if not h or not a:
                unknown.add(f"{me.home_disp} vs {me.away_disp}")
                continue
            kickoff = me.kickoff.astimezone(UTC).isoformat()
            date = kickoff[:10]
            if cfg.start_date <= date <= cfg.end_date:
                seen[(h, a, date)] = (h, a, kickoff)
    for u in sorted(unknown):
        print(f"  [WARN] equipos no mapeados (agregar alias): {u}")
    return list(seen.values())


def next_fixture_id(con: sqlite3.Connection) -> int:
    row = con.execute(
        "SELECT MAX(CAST(SUBSTR(id, 5) AS INTEGER)) FROM fixture "
        "WHERE tournament_id=? AND id LIKE 'lmx_%'", (TID,)).fetchone()
    return (row[0] or 0) + 1


def sync_fixtures(con: sqlite3.Connection, matches: list[tuple[str, str, str]]) -> tuple[int, int]:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    added = updated = 0
    n = next_fixture_id(con)
    for home, away, kickoff in sorted(matches, key=lambda m: m[2]):
        date = kickoff[:10]
        row = con.execute(
            "SELECT id, kickoff_utc FROM fixture WHERE tournament_id=? AND "
            "home_team_id=? AND away_team_id=? AND SUBSTR(kickoff_utc,1,10)=?",
            (TID, home, away, date)).fetchone()
        if row:
            if row[1] != kickoff:
                con.execute("UPDATE fixture SET kickoff_utc=?, fetched_at=? WHERE id=?",
                            (kickoff, now, row[0]))
                updated += 1
                print(f"  [UPD] {row[0]}: kickoff {row[1]} -> {kickoff}")
            continue
        fid = f"lmx_{n:03d}"
        n += 1
        con.execute(
            "INSERT INTO fixture(id, tournament_id, phase_id, home_team_id, away_team_id, "
            "kickoff_utc, status, neutral_venue, fetched_at) "
            "VALUES(?, ?, 'regular', ?, ?, ?, 'scheduled', 0, ?)",
            (fid, TID, home, away, kickoff, now))
        added += 1
        print(f"  [ADD] {fid}: {home} vs {away}  {kickoff}")
    return added, updated


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--include-closed", action="store_true",
        help="combina mercados cerrados y abiertos del Apertura 2026",
    )
    a = ap.parse_args()

    matches = discover_matches(include_closed=a.include_closed)
    print(f"\n=== Liga MX ingest — {len(matches)} partidos en Polymarket "
          f"({'APPLY' if a.apply else 'dry-run'}) ===\n")

    con = sqlite3.connect(DB)
    try:
        ensure_base_rows(con)
        added, updated = sync_fixtures(con, matches)
        if a.apply:
            con.commit()
        else:
            con.rollback()
        total = con.execute("SELECT COUNT(*) FROM fixture WHERE tournament_id=?", (TID,)).fetchone()[0]
        teams = con.execute("SELECT COUNT(*) FROM team WHERE tournament_id=?", (TID,)).fetchone()[0]
    finally:
        con.close()
    print(f"\n  Resumen: +{added} fixtures, ~{updated} actualizados · "
          f"en DB: {total} fixtures, {teams} equipos")
    if not a.apply:
        print("  (dry-run: rollback — nada escrito. Aplicar con --apply)")


if __name__ == "__main__":
    main()
