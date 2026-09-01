-- DDL canónico para fútbol americano (NFL).
-- Contrato que adapters/american_football/db_reader.py espera encontrar.

-- ─────────────────────────────────────────────
-- TORNEO / TEMPORADA
-- ─────────────────────────────────────────────
CREATE TABLE tournament (
    id              TEXT PRIMARY KEY,       -- "nfl_2026"
    name            TEXT NOT NULL,
    sport           TEXT NOT NULL,          -- "american_football"
    season_year     INTEGER NOT NULL,
    start_date      DATE,
    end_date        DATE,
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- CONFERENCIA / DIVISIÓN
-- ─────────────────────────────────────────────
CREATE TABLE conference (
    id              TEXT PRIMARY KEY,       -- "AFC" | "NFC"
    name            TEXT NOT NULL
);

CREATE TABLE division (
    id              TEXT PRIMARY KEY,       -- "AFC_NORTH" | "NFC_SOUTH"
    conference_id   TEXT REFERENCES conference(id),
    name            TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- EQUIPO (franquicia NFL)
-- ─────────────────────────────────────────────
CREATE TABLE team (
    id              TEXT PRIMARY KEY,       -- "KC" | "SF" | "DAL"
    tournament_id   TEXT REFERENCES tournament(id),
    name            TEXT NOT NULL,
    city            TEXT,
    division_id     TEXT REFERENCES division(id),
    elo_rating      REAL,
    spread_rating   REAL,                  -- rating basado en spreads históricos
    coach           TEXT,
    stadium         TEXT,
    dome_stadium    BOOLEAN DEFAULT FALSE   -- relevante para clima
);

-- ─────────────────────────────────────────────
-- JUGADOR
-- ─────────────────────────────────────────────
CREATE TABLE player (
    id              TEXT PRIMARY KEY,
    tournament_id   TEXT REFERENCES tournament(id),
    team_id         TEXT REFERENCES team(id),
    name            TEXT NOT NULL,
    position        TEXT NOT NULL,
    -- "QB" | "RB" | "WR" | "TE" | "OL" | "DL" | "LB" | "CB" | "S" | "K" | "P"
    jersey_number   INTEGER,
    depth_chart_rank INTEGER,              -- 1=starter, 2=backup, etc.
    age             INTEGER,
    years_exp       INTEGER,
    status          TEXT DEFAULT 'active'
    -- "active" | "injured_ir" | "injured_q" | "suspended" | "practice_squad"
);

-- ─────────────────────────────────────────────
-- SEMANA / FASE
-- ─────────────────────────────────────────────
CREATE TABLE week (
    id              TEXT PRIMARY KEY,       -- "regular_w1" | "wildcard" | "divisional" | "conf_champ" | "superbowl"
    tournament_id   TEXT REFERENCES tournament(id),
    week_number     INTEGER,
    phase           TEXT NOT NULL,         -- "preseason" | "regular" | "wildcard" | "divisional" | "conference" | "superbowl"
    start_date      DATE,
    end_date        DATE
);

-- ─────────────────────────────────────────────
-- PARTIDO (game)
-- ─────────────────────────────────────────────
CREATE TABLE fixture (
    id              TEXT PRIMARY KEY,
    tournament_id   TEXT REFERENCES tournament(id),
    week_id         TEXT REFERENCES week(id),
    home_team_id    TEXT REFERENCES team(id),
    away_team_id    TEXT REFERENCES team(id),
    kickoff_utc     TIMESTAMP NOT NULL,
    stadium         TEXT,
    dome_game       BOOLEAN DEFAULT FALSE,
    is_international BOOLEAN DEFAULT FALSE, -- London, Munich, etc.
    status          TEXT DEFAULT 'scheduled',

    -- Resultado
    home_score      INTEGER,
    away_score      INTEGER,
    winner_team_id  TEXT REFERENCES team(id),
    went_to_ot      BOOLEAN DEFAULT FALSE,

    -- Líneas de Vegas (contexto para los modelos)
    spread_home     REAL,                  -- spread de apertura, home team (negativo = favorito)
    spread_open     REAL,
    total_ou        REAL,                  -- over/under total de puntos
    moneyline_home  INTEGER,               -- en formato americano (-150, +130)
    moneyline_away  INTEGER,

    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- ESTADÍSTICAS DEL PARTIDO POR EQUIPO
-- ─────────────────────────────────────────────
CREATE TABLE match_team_stat (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id      TEXT REFERENCES fixture(id),
    team_id         TEXT REFERENCES team(id),
    total_yards     INTEGER,
    passing_yards   INTEGER,
    rushing_yards   INTEGER,
    turnovers       INTEGER,
    time_of_poss_sec INTEGER,
    third_down_pct  REAL,
    red_zone_pct    REAL,
    sacks_allowed   INTEGER,
    penalties       INTEGER,
    penalty_yards   INTEGER,
    plays           INTEGER,
    offensive_epa_per_play REAL,
    defensive_epa_per_play REAL,          -- EPA evitado por jugada; mayor = mejor
    success_rate    REAL,
    explosive_play_rate REAL,             -- proporción de jugadas con 20+ yardas
    pass_rate       REAL,
    proe            REAL,                 -- pass rate over expected de nflverse
    UNIQUE(fixture_id, team_id)
);

-- ─────────────────────────────────────────────
-- ESTADÍSTICAS POR JUGADOR (posición específica)
-- ─────────────────────────────────────────────
CREATE TABLE match_player_stat (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id      TEXT REFERENCES fixture(id),
    player_id       TEXT REFERENCES player(id),
    team_id         TEXT REFERENCES team(id),
    snap_count      INTEGER,
    snap_pct        REAL,
    -- QB
    pass_attempts   INTEGER,
    pass_completions INTEGER,
    pass_yards      INTEGER,
    pass_tds        INTEGER,
    interceptions   INTEGER,
    passer_rating   REAL,
    -- RB/WR/TE
    rush_attempts   INTEGER,
    rush_yards      INTEGER,
    rush_tds        INTEGER,
    targets         INTEGER,
    receptions      INTEGER,
    receiving_yards INTEGER,
    receiving_tds   INTEGER,
    -- DEF
    tackles         INTEGER,
    sacks           REAL,
    forced_fumbles  INTEGER,
    interceptions_def INTEGER
);

-- ─────────────────────────────────────────────
-- STANDING SEMANAL
-- ─────────────────────────────────────────────
CREATE TABLE standing (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id   TEXT REFERENCES tournament(id),
    week_id         TEXT REFERENCES week(id),
    team_id         TEXT REFERENCES team(id),
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    ties            INTEGER DEFAULT 0,
    pf              INTEGER DEFAULT 0,     -- points for
    pa              INTEGER DEFAULT 0,     -- points against
    div_rank        INTEGER,
    playoff_seed    INTEGER                -- NULL si no clasificó
);

-- ─────────────────────────────────────────────
-- INJURY REPORT (mandatorio en NFL, sale jueves)
-- ─────────────────────────────────────────────
CREATE TABLE injury_report (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       TEXT REFERENCES player(id),
    fixture_id      TEXT REFERENCES fixture(id),
    injury_type     TEXT,                  -- "knee" | "hamstring" | "concussion" | etc.
    practice_status TEXT,                  -- "FP" | "LP" | "DNP" (full/limited/did not practice)
    game_status     TEXT,                  -- "Questionable" | "Doubtful" | "Out" | "IR" | NULL(probable)
    reported_at     TIMESTAMP,
    source          TEXT
);

-- ─────────────────────────────────────────────
-- ELO HISTÓRICO Y METADATA DE INGESTA
-- ─────────────────────────────────────────────
CREATE TABLE elo_rating_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id         TEXT REFERENCES team(id),
    after_fixture_id TEXT REFERENCES fixture(id),
    elo_before      REAL,
    elo_after       REAL,
    rated_at        TIMESTAMP
);

CREATE TABLE ingest_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id   TEXT,
    source          TEXT NOT NULL,
    entity_type     TEXT NOT NULL,
    records_inserted INTEGER DEFAULT 0,
    records_updated  INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'ok',
    error_msg       TEXT,
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
