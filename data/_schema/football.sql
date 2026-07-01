-- DDL canónico para fútbol asociación.
-- Es el contrato que adapters/football/db_reader.py espera encontrar.
-- TODOS los torneos de fútbol deben implementar estas tablas.

-- ─────────────────────────────────────────────
-- TORNEO
-- ─────────────────────────────────────────────
CREATE TABLE tournament (
    id              TEXT PRIMARY KEY,       -- "fifa_world_cup_2026"
    name            TEXT NOT NULL,
    sport           TEXT NOT NULL,          -- "football"
    format          TEXT NOT NULL,          -- "world_cup" | "league" | "cup" | "champions"
    start_date      DATE NOT NULL,
    end_date        DATE,
    host_country    TEXT,
    n_teams         INTEGER,
    source_url      TEXT,                   -- URL original de donde vienen los datos
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- FASE / RONDA
-- ─────────────────────────────────────────────
CREATE TABLE phase (
    id              TEXT PRIMARY KEY,       -- "group_stage" | "r16" | "qf" | "sf" | "final"
    tournament_id   TEXT REFERENCES tournament(id),
    name            TEXT NOT NULL,
    phase_order     INTEGER,               -- 1=grupos, 2=r16, etc.
    is_knockout     BOOLEAN DEFAULT FALSE
);

-- ─────────────────────────────────────────────
-- EQUIPO / SELECCIÓN
-- ─────────────────────────────────────────────
CREATE TABLE team (
    id              TEXT PRIMARY KEY,       -- "MEX", "BRA", "club_america_2026"
    tournament_id   TEXT REFERENCES tournament(id),
    name            TEXT NOT NULL,
    short_name      TEXT,
    country_code    TEXT,                   -- ISO 3166-1 alpha-3
    group_id        TEXT,                  -- NULL si no aplica (ligas)
    confederation   TEXT,                  -- "CONMEBOL" | "UEFA" | "CONCACAF" | etc.
    elo_rating      REAL,                  -- rating Elo al inicio del torneo
    fifa_rank       INTEGER,
    coach           TEXT
);

-- ─────────────────────────────────────────────
-- GRUPO (aplica a World Cup, Champions group stage, etc.)
-- ─────────────────────────────────────────────
CREATE TABLE group_table (
    id              TEXT PRIMARY KEY,       -- "A", "B", ... | NULL para ligas sin grupos
    tournament_id   TEXT REFERENCES tournament(id),
    name            TEXT NOT NULL
);

-- ─────────────────────────────────────────────
-- JUGADOR
-- ─────────────────────────────────────────────
CREATE TABLE player (
    id              TEXT PRIMARY KEY,       -- "messi_10_arg" o ID externo
    tournament_id   TEXT REFERENCES tournament(id),
    team_id         TEXT REFERENCES team(id),
    name            TEXT NOT NULL,
    short_name      TEXT,
    nationality     TEXT,
    position        TEXT,                  -- "GK" | "DEF" | "MID" | "FWD"
    jersey_number   INTEGER,
    age             INTEGER,
    market_value_eur REAL,                 -- en millones EUR, NULL si no disponible
    is_captain      BOOLEAN DEFAULT FALSE,
    status          TEXT DEFAULT 'available'  -- "available" | "injured" | "suspended" | "doubtful"
);

-- ─────────────────────────────────────────────
-- FIXTURE / PARTIDO
-- ─────────────────────────────────────────────
CREATE TABLE fixture (
    id              TEXT PRIMARY KEY,
    tournament_id   TEXT REFERENCES tournament(id),
    phase_id        TEXT REFERENCES phase(id),
    group_id        TEXT REFERENCES group_table(id),  -- NULL en knockout
    home_team_id    TEXT REFERENCES team(id),
    away_team_id    TEXT REFERENCES team(id),
    kickoff_utc     TIMESTAMP NOT NULL,
    venue           TEXT,
    city            TEXT,
    country         TEXT,
    status          TEXT DEFAULT 'scheduled',
    -- "scheduled" | "live" | "finished" | "postponed" | "cancelled"

    -- Resultado (NULL hasta que termine)
    home_goals      INTEGER,
    away_goals      INTEGER,
    home_goals_et   INTEGER,               -- extra time
    away_goals_et   INTEGER,
    home_goals_pen  INTEGER,               -- penalties
    away_goals_pen  INTEGER,
    winner_team_id  TEXT REFERENCES team(id),  -- NULL si empate en fase grupos

    -- Contexto para los modelos
    weather_temp_c  REAL,
    weather_condition TEXT,               -- "clear" | "rain" | "humid" | etc.
    attendance      INTEGER,
    referee         TEXT,
    neutral_venue   BOOLEAN DEFAULT FALSE,

    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- ESTADÍSTICAS DEL PARTIDO POR EQUIPO
-- ─────────────────────────────────────────────
CREATE TABLE match_team_stat (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id      TEXT REFERENCES fixture(id),
    team_id         TEXT REFERENCES team(id),
    shots_total     INTEGER,
    shots_on_target INTEGER,
    possession_pct  REAL,
    passes_total    INTEGER,
    pass_accuracy   REAL,
    corners         INTEGER,
    fouls           INTEGER,
    yellow_cards    INTEGER,
    red_cards       INTEGER,
    offsides        INTEGER,
    xg              REAL                   -- expected goals, NULL si no disponible
);

-- ─────────────────────────────────────────────
-- ESTADÍSTICAS DEL PARTIDO POR JUGADOR
-- ─────────────────────────────────────────────
CREATE TABLE match_player_stat (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id      TEXT REFERENCES fixture(id),
    player_id       TEXT REFERENCES player(id),
    team_id         TEXT REFERENCES team(id),
    minutes_played  INTEGER,
    goals           INTEGER DEFAULT 0,
    assists         INTEGER DEFAULT 0,
    yellow_cards    INTEGER DEFAULT 0,
    red_cards       INTEGER DEFAULT 0,
    shots           INTEGER DEFAULT 0,
    shots_on_target INTEGER DEFAULT 0,
    key_passes      INTEGER DEFAULT 0,
    dribbles_success INTEGER DEFAULT 0,
    rating          REAL,                  -- rating del partido (ej: SofaScore 0-10)
    was_starter     BOOLEAN DEFAULT TRUE
);

-- ─────────────────────────────────────────────
-- CLASIFICACIÓN / STANDING (para ligas y fase de grupos)
-- ─────────────────────────────────────────────
CREATE TABLE standing (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id   TEXT REFERENCES tournament(id),
    group_id        TEXT REFERENCES group_table(id),
    team_id         TEXT REFERENCES team(id),
    matchday        INTEGER,               -- jornada (NULL = standing actual)
    played          INTEGER DEFAULT 0,
    won             INTEGER DEFAULT 0,
    drawn           INTEGER DEFAULT 0,
    lost            INTEGER DEFAULT 0,
    goals_for       INTEGER DEFAULT 0,
    goals_against   INTEGER DEFAULT 0,
    goal_diff       INTEGER GENERATED ALWAYS AS (goals_for - goals_against),
    points          INTEGER DEFAULT 0,
    position        INTEGER,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- LESIONES / SUSPENSIONES (afectan los modelos)
-- ─────────────────────────────────────────────
CREATE TABLE player_availability (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       TEXT REFERENCES player(id),
    tournament_id   TEXT REFERENCES tournament(id),
    status          TEXT NOT NULL,         -- "injured" | "suspended" | "doubtful" | "available"
    reason          TEXT,
    reported_at     TIMESTAMP,
    expected_return DATE,                  -- NULL si indefinido
    source          TEXT                   -- URL o fuente de la noticia
);

-- ─────────────────────────────────────────────
-- RATINGS ELO HISTÓRICOS (serie temporal por equipo)
-- ─────────────────────────────────────────────
CREATE TABLE elo_rating_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id         TEXT REFERENCES team(id),
    tournament_id   TEXT REFERENCES tournament(id),
    after_fixture_id TEXT REFERENCES fixture(id),
    elo_before      REAL NOT NULL,
    elo_after       REAL NOT NULL,
    elo_delta       REAL GENERATED ALWAYS AS (elo_after - elo_before),
    rated_at        TIMESTAMP
);

-- ─────────────────────────────────────────────
-- METADATA DE INGESTA (auditoría de fuentes)
-- ─────────────────────────────────────────────
CREATE TABLE ingest_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tournament_id   TEXT,
    source          TEXT NOT NULL,         -- "api_football" | "fbref" | "manual" | "sofascore"
    entity_type     TEXT NOT NULL,         -- "fixture" | "player" | "stat" | "standing"
    records_inserted INTEGER DEFAULT 0,
    records_updated  INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'ok',     -- "ok" | "partial" | "failed"
    error_msg       TEXT,
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
