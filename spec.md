# WHITEPAPER — Sports Quant Trading System
**Un hedge fund sintético asistido por Claude para operar mercados de predicción deportivos en Polymarket**

Versión 0.3 — Junio 2026

---

## 1. Visión

Este sistema convierte repos de modelos deportivos en infraestructura operativa de trading. No es un bot. Es un **hedge fund sintético de un operador** donde Claude actúa como analista cuantitativo, gestor de riesgo, y operador de ejecución — con el humano como CIO que aprueba decisiones en condiciones ambiguas y delega las obvias.

El sistema está diseñado para ser **extensible a cualquier torneo o liga deportiva**. El torneo activo (FIFA World Cup 2026, NFL 2026, etc.) es un parámetro de configuración, no un supuesto hardcodeado. Agregar un deporte nuevo significa crear una estrategia nueva y un adaptador de datos — el pipeline de áreas permanece idéntico.

El principio rector es **reproducibilidad hacia adelante**: cada decisión de trading es el resultado determinístico de inputs documentados procesados por funciones versionadas con contratos de datos explícitos. Si se repiten los mismos inputs, se obtiene la misma decisión. Esto elimina la ambigüedad, hace el sistema auditable, y permite que Claude opere sobre él sin riesgo de duplicidad o estado inconsistente.

---

## 2. Principios de Diseño

### 2.1 Tres pilares verticales que atraviesan todas las áreas

```
ÁREA (ej: Risk)
├── functions/          ← código Python puro, sin estado, testeable
│   ├── __init__.py
│   ├── kelly.py
│   ├── drawdown.py
│   └── exposure.py
├── schemas/            ← Pydantic models, contratos de datos
│   ├── __init__.py
│   ├── position_risk.py
│   └── trade_signal.py
└── SKILL.md            ← contexto para Claude Code sobre esta área
```

**Functions:** funciones puras Python. Reciben datos, regresan datos. Sin side effects. Sin imports de otras áreas (solo de `core/`). Esto las hace 100% testeables en aislamiento y reutilizables por Claude en cualquier contexto.

**Schemas:** modelos Pydantic que definen el contrato de entrada y salida de cada función. Son la única fuente de verdad del tipo de dato que fluye entre áreas. Si un schema cambia, el sistema falla ruidosamente antes de ejecutar — esto es la idempotencia.

**SKILL.md:** documento de contexto que Claude Code lee antes de operar dentro de un área. Define qué hace el área, qué funciones existen, qué schemas consume y produce, qué hooks la activan, y qué restricciones aplican. Es el manual de operación del área para el agente.

### 2.2 Flujo unidireccional (no hay ciclos entre áreas)

```
Research → Optimization → Risk → Execution → Portfolio → Editorial
              ↑                        ↓
         [Strategy.md]          [Django App State]
```

Research produce señales. Optimization las calibra. Risk las filtra. Execution las opera. Portfolio las registra. Editorial las comunica. El estado vive **únicamente en el Django App** — ningún área escribe estado propio.

### 2.3 Dos modos de operación de Claude

| Modo | Condición | Acción de Claude |
|---|---|---|
| **AUTO** | Workflow aprobado + reglas cuantitativas satisfechas | Ejecuta sin intervención |
| **REVIEW** | Condición ambigua / regla híbrida con componente cualitativo | Redacta recomendación estructurada + espera aprobación |

Un workflow se "aprueba" cuando: (a) tiene una Strategy.md con reglas formalizadas, (b) fue ejecutado manualmente al menos 1 vez sin errores, (c) el humano lo marca como `status: approved` en el Django App.

---

## 3. Estructura del Repositorio

```
sports-quant-trading/
├── WHITEPAPER.md
├── README.md
├── CLAUDE.md                               # contexto global del repo para Claude Code
├── pyproject.toml
├── .env.example
│
├── core/                                   # utilidades compartidas, sin lógica de negocio
│   ├── __init__.py
│   ├── types.py                            # tipos base: Decimal, Timestamp, WalletAddress, SportType
│   ├── exceptions.py
│   ├── utils.py
│   └── django_client.py                    # cliente HTTP para el Django App
│
├── data/                                   # ← NUEVO: datos crudos por torneo (SQLite)
│   ├── README.md                           # cómo está organizado cada SQLite
│   ├── _schema/                            # schemas SQL canónicos por deporte
│   │   ├── football.sql                    # DDL canónico para fútbol asociación
│   │   └── american_football.sql           # DDL canónico para fútbol americano
│   ├── fifa_world_cup_2026/
│   │   ├── fifa_world_cup_2026.sqlite      # base de datos del torneo
│   │   ├── DATA_SOURCES.md                 # de dónde vienen los datos, cómo actualizarlos
│   │   └── ingest/                         # scripts de ingesta específicos de este torneo
│   │       ├── fetch_fixtures.py
│   │       ├── fetch_squads.py
│   │       └── fetch_live_stats.py
│   └── nfl_2026/
│       ├── nfl_2026.sqlite
│       ├── DATA_SOURCES.md
│       └── ingest/
│           ├── fetch_schedule.py
│           ├── fetch_rosters.py
│           └── fetch_game_stats.py
│
├── tournaments/                            # configuración por torneo/liga
│   ├── README.md
│   ├── registry.py                         # registro global: {tournament_id → TournamentConfig}
│   ├── _template/
│   │   ├── TOURNAMENT.md
│   │   ├── adapter.py
│   │   └── STRATEGY.md
│   ├── fifa_world_cup_2026/
│   │   ├── TOURNAMENT.md
│   │   ├── adapter.py                      # apunta a data/fifa_world_cup_2026/
│   │   └── strategies/
│   │       ├── match_winner_v1/
│   │       │   └── STRATEGY.md
│   │       └── top_scorer_v1/
│   │           └── STRATEGY.md
│   └── nfl_2026/
│       ├── TOURNAMENT.md
│       ├── adapter.py                      # apunta a data/nfl_2026/
│       └── strategies/
│           └── game_winner_v1/
│               └── STRATEGY.md
│
├── adapters/                               # capa de acceso a datos — lee los SQLite
│   ├── base.py                             # SportDataAdapter ABC
│   ├── SKILL.md                            # ← contexto del área para Claude Code
│   ├── football/
│   │   ├── __init__.py
│   │   ├── db_reader.py                    # queries genéricas sobre football.sql schema
│   │   ├── elo_loader.py                   # carga modelos Elo desde el SQLite
│   │   ├── bayes_loader.py
│   │   ├── trueskill_loader.py
│   │   └── cross_tournament_joiner.py      # ← join agentico entre torneos de football
│   └── american_football/
│       ├── __init__.py
│       ├── db_reader.py
│       └── elo_loader.py
│
├── research/
│   ├── SKILL.md
│   ├── functions/
│   │   ├── model_loader.py
│   │   ├── probability_extractor.py
│   │   ├── market_scanner.py
│   │   └── edge_screener.py
│   ├── schemas/
│   │   ├── match_prediction.py
│   │   ├── market_opportunity.py
│   │   └── research_report.py
│   └── notebooks/
│
├── risk/
│   ├── SKILL.md
│   ├── functions/
│   │   ├── kelly.py
│   │   ├── exposure.py
│   │   ├── drawdown.py
│   │   └── correlation.py
│   └── schemas/
│       ├── position_risk.py
│       ├── kelly_output.py
│       └── risk_verdict.py
│
├── optimization/
│   ├── SKILL.md
│   ├── functions/
│   │   ├── bet_sizer.py
│   │   ├── portfolio_optimizer.py
│   │   └── threshold_calibrator.py
│   └── schemas/
│       ├── sizing_input.py
│       ├── sizing_output.py
│       └── optimization_result.py
│
├── execution/
│   ├── SKILL.md
│   ├── functions/
│   │   ├── order_builder.py
│   │   ├── price_validator.py
│   │   ├── slippage_estimator.py
│   │   └── order_classifier.py
│   └── schemas/
│       ├── trade_intent.py
│       ├── trade_order.py
│       ├── execution_decision.py
│       └── order_result.py
│
├── portfolio/
│   ├── SKILL.md
│   ├── functions/
│   │   ├── pnl_calculator.py
│   │   ├── position_tracker.py
│   │   └── performance_metrics.py
│   └── schemas/
│       ├── portfolio_state.py
│       ├── position.py
│       └── performance_summary.py
│
├── editorial/
│   ├── SKILL.md
│   ├── functions/
│   │   ├── report_builder.py
│   │   ├── trade_narrator.py
│   │   └── performance_digest.py
│   ├── schemas/
│   │   ├── trade_report.py
│   │   └── weekly_digest.py
│   └── reports/
│       └── {tournament_id}/
│           └── YYYY-MM-DD_digest.md
│
├── agent/
│   ├── CLAUDE.md
│   ├── HOOKS.md
│   ├── tools/
│   │   ├── research_tools.py
│   │   ├── risk_tools.py
│   │   ├── execution_tools.py
│   │   ├── portfolio_tools.py
│   │   └── django_sync_tools.py
│   ├── workflows/
│   │   ├── full_analysis.py
│   │   ├── quick_scan.py
│   │   └── post_event_review.py
│   └── prompts/
│       ├── analysis_prompt.md
│       ├── review_prompt.md
│       └── report_prompt.md
│
└── tests/
    ├── unit/
    └── integration/
        └── django_sync/
```

---

## 4. Capa de Datos — `data/` y `adapters/`

### 4.1 Principio: un SQLite por torneo

Cada torneo tiene su propio archivo `.sqlite` aislado. Un archivo por torneo significa:

- Puedes borrarlo, reemplazarlo, o experimentar con él sin afectar otros torneos
- Es versionable en git (con git-lfs para archivos grandes)
- Claude Code lo puede leer directo con sqlite3 — sin servidor, sin credenciales
- El aislamiento hace que la fuente de datos sea explícita: no hay ambigüedad de qué datos corresponden a qué torneo

El "join agentico" entre torneos no es SQL — es Python en la capa `adapters/cross_tournament_joiner.py`. Esto es intencional: los joins entre torneos tienen semántica deportiva (¿cómo comparo el rendimiento de Messi en el Mundial vs Champions?) que no se puede expresar limpiamente en SQL cross-file. Claude lo hace en memoria.

### 4.2 Schema DDL canónico para fútbol (`data/_schema/football.sql`)

Este DDL define las tablas que **todos** los torneos de fútbol asociación deben implementar. Es el contrato que `adapters/football/db_reader.py` espera encontrar.

```sql
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
```

### 4.3 Schema DDL canónico para fútbol americano (`data/_schema/american_football.sql`)

```sql
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
    penalty_yards   INTEGER
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
-- (mismo patrón que football.sql)
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
```

### 4.4 `DATA_SOURCES.md` — Formato canónico por torneo

Cada `data/{tournament_id}/DATA_SOURCES.md` documenta exactamente de dónde vienen los datos y cómo actualizarlos. Cuando haya fuente, cuando no la haya, Claude sabe qué hacer.

```markdown
# DATA_SOURCES — {tournament_id}

## Estado de datos
| Tabla | Fuente actual | Cobertura | Frecuencia actualización | Script de ingesta |
|---|---|---|---|---|
| tournament | Manual | 100% | Una vez | — |
| team | Manual / FIFA API | 100% | Una vez | fetch_squads.py |
| player | Transfermarkt scrape | 90% | Pre-torneo | fetch_squads.py |
| fixture | API-Football.com | 100% | Diaria | fetch_fixtures.py |
| match_team_stat | API-Football.com | Post-partido | Por partido | fetch_live_stats.py |
| match_player_stat | Sofascore (manual) | 60% | Por partido | — (pendiente automatizar) |
| player_availability | Manual + Twitter | Best effort | Diaria | — |
| elo_rating_history | Calculado localmente | 100% | Post-partido | calculado por el modelo |

## Fuentes pendientes de confirmar
- match_player_stat: evaluar FBref, Understat, o Opta
- player_availability en tiempo real: evaluar Rotoworld API o scraping

## Cómo actualizar antes de un partido
1. `python data/fifa_world_cup_2026/ingest/fetch_fixtures.py` — actualiza fixtures
2. `python data/fifa_world_cup_2026/ingest/fetch_squads.py` — actualiza lesiones
3. Verificar manualmente `player_availability` para figuras clave

## Notas
- Los datos de player_availability son best-effort — siempre activarán QR-002 en la estrategia
- Los ratings Elo se calculan post-partido por los modelos del repo, no se ingiestan de fuente externa
```

### 4.5 `adapters/football/db_reader.py` — Queries canónicas

```python
"""
Queries genéricas sobre el schema football.sql.
Agnóstico al torneo — recibe tournament_id como parámetro.
No contiene lógica de negocio — solo acceso a datos.
"""
import sqlite3
from pathlib import Path
from typing import Optional

def get_db_path(tournament_id: str) -> Path:
    return Path(f"data/{tournament_id}/{tournament_id}.sqlite")

class FootballDBReader:
    def __init__(self, tournament_id: str):
        self.tournament_id = tournament_id
        self.db_path = get_db_path(tournament_id)
        if not self.db_path.exists():
            raise FileNotFoundError(f"SQLite no encontrado: {self.db_path}")

    def get_fixture(self, fixture_id: str) -> dict | None:
        """Partido con equipos y fase."""

    def get_upcoming_fixtures(self, hours_ahead: int = 24) -> list[dict]:
        """Partidos programados en las próximas N horas."""

    def get_team(self, team_id: str) -> dict | None:
        """Equipo con su Elo actual y contexto."""

    def get_squad(self, team_id: str) -> list[dict]:
        """Plantel del equipo con status de disponibilidad."""

    def get_player_availability(self, team_id: str) -> list[dict]:
        """Jugadores con status != 'available'."""

    def get_head_to_head(self, team_a: str, team_b: str, limit: int = 10) -> list[dict]:
        """Últimos N partidos entre dos equipos."""

    def get_team_form(self, team_id: str, last_n: int = 5) -> list[dict]:
        """Últimos N partidos del equipo con resultado."""

    def get_elo_history(self, team_id: str) -> list[dict]:
        """Serie histórica de ratings Elo del equipo."""

    def get_standing(self, group_id: str = None) -> list[dict]:
        """Tabla de posiciones, opcionalmente filtrada por grupo."""
```

### 4.6 `adapters/football/cross_tournament_joiner.py` — Join agentico

```python
"""
Join en Python entre torneos del mismo deporte.
No es SQL — es semántica deportiva.
Ejemplos de uso:
  - Comparar forma de un equipo en World Cup vs sus partidos de clasificación
  - Enriquecer el análisis de un partido con estadísticas históricas de un jugador
    en torneos anteriores
"""

class FootballCrossTournamentJoiner:

    def get_player_cross_tournament_stats(
        self,
        player_id: str,
        tournament_ids: list[str]
    ) -> dict:
        """
        Estadísticas de un jugador en múltiples torneos.
        Útil para: "¿cómo le va a Messi en partidos de eliminación directa?"
        """

    def get_team_historical_elo(
        self,
        team_id: str,
        tournament_ids: list[str]
    ) -> list[dict]:
        """
        Serie Elo de un equipo a través de múltiples torneos.
        Permite ver tendencia de largo plazo.
        """

    def get_h2h_across_tournaments(
        self,
        team_a: str,
        team_b: str,
        tournament_ids: list[str]
    ) -> list[dict]:
        """
        Head-to-head histórico entre dos equipos en cualquier torneo registrado.
        """
```

### 4.7 `adapters/SKILL.md`

```markdown
# SKILL: Adapters (Capa de Datos)

## ROL EN EL SISTEMA
Proveer acceso a los datos del torneo almacenados en SQLite.
Es la única capa que toca los archivos .sqlite — ninguna otra área
accede directamente a los datos crudos.

## CUÁNDO INVOCAR
- Research necesita datos del partido antes de calcular edge
- Se necesita verificar disponibilidad de jugadores (activa QR-002)
- Se requiere historial head-to-head para contexto cualitativo
- Claude necesita hacer un join entre torneos del mismo deporte

## CUÁNDO NO INVOCAR
- Para datos de Polymarket (eso es CLOB API vía research/)
- Para estado del portafolio (eso es portfolio/ vía django_client)
- Para escribir resultados de trading (los adapters son read-only)

## READERS DISPONIBLES

| Clase | Deporte | Archivo |
|---|---|---|
| `FootballDBReader` | Fútbol asociación | `adapters/football/db_reader.py` |
| `AmericanFootballDBReader` | NFL | `adapters/american_football/db_reader.py` |
| `FootballCrossTournamentJoiner` | Cross-torneo fútbol | `adapters/football/cross_tournament_joiner.py` |

## INSTANCIACIÓN
```python
# Siempre pasar tournament_id explícito
reader = FootballDBReader(tournament_id="fifa_world_cup_2026")
fixture = reader.get_fixture("match_123")
```

## CONSTRAINTS
- NUNCA escribir en el SQLite desde esta capa (read-only)
- Si el archivo SQLite no existe → FileNotFoundError inmediato, no silencioso
- Si player_availability retorna jugadores con status != available → 
  SIEMPRE incluir como qualitative_flag QR-002 en el RiskVerdict
- Los datos de player_availability son best-effort: pueden estar desactualizados

## ERRORES COMUNES
- Asumir que el fixture_id del SQLite es el mismo que el condition_id de Polymarket (NO lo son)
- Usar cross_tournament_joiner cuando solo hay un torneo (overhead innecesario)
- No verificar que el SQLite existe antes de instanciar el reader
```

---

Este es el documento más importante del sistema. Es la única fuente de verdad de las reglas de trading para una combinación específica de `torneo × tipo de mercado`. Claude lo lee antes de cada decisión. Tiene formato estricto para ser parseable tanto por humanos como por el agente.

Cada torneo puede tener múltiples estrategias (Match Winner, Top Scorer, Over/Under, etc.). Cada una vive en su propio `STRATEGY.md` bajo `tournaments/{tournament_id}/strategies/{strategy_id}/`.

```markdown
# STRATEGY: {Nombre descriptivo}

## HEADER (parseado por el agente — campos obligatorios)
version: 0.1
status: draft             # draft | under_review | approved | deprecated
author: Guillermo Izquierdo
last_updated: 2026-06-15

## SCOPE
tournament_id: fifa_world_cup_2026   # debe existir en tournaments/registry.py
sport: football                      # football | american_football | basketball | ...
market_type: match_winner            # el tipo de mercado de Polymarket que cubre
venue: Polymarket
outcomes: [HOME_WIN, DRAW, AWAY_WIN] # outcomes válidos para esta estrategia

## THESIS
[Párrafo libre. Explica por qué existe el edge. Claude lo lee para contexto cualitativo.]

---

## SIGNAL DEFINITION

### Fuentes de probabilidad
- model_probability: output del ensemble del repo vinculado (campo específico por adaptador)
- market_probability: midpoint del token YES en Polymarket CLOB API
- edge: model_probability - market_probability

### Thresholds de decisión
- edge_threshold_auto: 0.08        # edge >= X → modo AUTO
- edge_threshold_review: 0.04      # edge [X, Y) → modo REVIEW
- edge_threshold_discard: 0.04     # edge < X → descartar
- min_market_volume_usdc: 5000
- max_hours_to_event: 24
- min_hours_to_event: 1

---

## ENTRY RULES

### AUTO (todas deben cumplirse — evaluación determinística)
- [ ] edge >= edge_threshold_auto
- [ ] market_volume >= min_market_volume_usdc
- [ ] hours_to_event BETWEEN min_hours_to_event AND max_hours_to_event
- [ ] portfolio.exposure_per_team < 0.15
- [ ] portfolio.total_open_positions < 10
- [ ] risk.kelly_fraction <= 0.05

### REVIEW (cualquiera activa modo REVIEW — requiere aprobación humana)
- [ ] edge BETWEEN edge_threshold_review AND edge_threshold_auto
- [ ] event_phase IN [playoff, knockout, final]    # mayor incertidumbre estructural
- [ ] model_confidence == "LOW"                     # n insuficiente de historia
- [ ] qualitative_flag_count > 0                   # ver QUALITATIVE RULES

### DISCARD (cualquiera descarta sin aprobación posible)
- [ ] edge < edge_threshold_discard
- [ ] market_volume < min_market_volume_usdc
- [ ] portfolio.drawdown_7d > 0.20
- [ ] hours_to_event < min_hours_to_event

---

## EXIT RULES

### Cierre automático
- Resolución del mercado (Polymarket cierra el mercado)
- Stop-loss por posición: pérdida unrealizada > 60% del valor inicial

### Cierre en REVIEW
- Precio cae a < 0.15 en posición YES comprada
- [Agregar reglas específicas del deporte aquí]

---

## SIZING
method: fractional_kelly
kelly_fraction: 0.25
max_bet_usdc: 50
min_bet_usdc: 5

---

## QUALITATIVE RULES
# Estas reglas Claude evalúa con contexto — activan modo REVIEW si aplican
# Formato: QR-{ID}: {descripción} → {acción si aplica}
- QR-001: Si el partido es "meaningless" (ambos equipos ya clasificados/eliminados) → reducir size 50%
- QR-002: Reportes de cambios tácticos o lesiones en últimas 6h → activar REVIEW
- QR-003: Condiciones climáticas extremas que afecten el modelo → mencionar en reporte
# [Agregar QRs específicas del deporte al crear la estrategia]

---

## PERFORMANCE TARGETS
win_rate_target: 0.55
roi_target: 0.15
max_drawdown_allowed: 0.25
evaluation_period: tournament     # tournament | season | rolling_30d
```

---

## 5. El Archivo `STRATEGY.md` — Formato Canónico

Este es el documento más importante del sistema. Es la única fuente de verdad de las reglas de trading para una combinación específica de `torneo × tipo de mercado`. Claude lo lee antes de cada decisión. Tiene formato estricto para ser parseable tanto por humanos como por el agente.

Cada torneo puede tener múltiples estrategias (Match Winner, Top Scorer, Over/Under, etc.). Cada una vive en su propio `STRATEGY.md` bajo `tournaments/{tournament_id}/strategies/{strategy_id}/`. El contenido canónico de este archivo se detalla en la sección de Workflows y Hooks — es el documento que Claude lee como primer paso de cualquier hook PIPELINE.

---

## 6. Schemas Clave — Contratos de Datos

Los schemas Pydantic son inmutables una vez aprobados. Se versionan con el mismo sistema que el código.

### 5.1 `MarketOpportunity` (Research → Optimization)
```python
from pydantic import BaseModel, field_validator
from decimal import Decimal
from datetime import datetime

class MarketOpportunity(BaseModel):
    """Output de research, input de optimization y risk. Agnóstico al deporte."""
    
    # Identificadores de Polymarket
    polymarket_condition_id: str
    polymarket_token_id: str
    outcome: str                        # "YES" | "NO"
    
    # Identificadores del evento deportivo (genéricos)
    tournament_id: str                  # ej: "fifa_world_cup_2026", "nfl_2026"
    sport: str                          # ej: "football", "american_football"
    event_id: str                       # ID en el repo del torneo
    market_type: str                    # ej: "match_winner", "over_under"
    strategy_id: str                    # estrategia que generó esta señal
    
    # Probabilidades
    model_probability: Decimal          # 0.0 - 1.0
    market_probability: Decimal         # 0.0 - 1.0
    edge: Decimal                       # model_probability - market_probability
    
    # Contexto del evento (genérico — aplica a cualquier deporte)
    participant_home: str               # equipo local / favorito / jugador 1
    participant_away: str               # equipo visitante / rival / jugador 2
    event_start_utc: datetime
    hours_to_event: float
    event_phase: str                    # "group" | "playoff" | "final" | "regular_season"
    
    # Contexto del mercado Polymarket
    market_volume_usdc: Decimal
    market_liquidity_usdc: Decimal
    
    # Metadata del modelo
    model_version: str
    model_confidence: str               # "HIGH" | "MEDIUM" | "LOW"
    sample_size: int                    # partidos históricos usados
    
    # Timestamp y versión para idempotencia y auditoría
    generated_at: datetime
    strategy_version: str              # version del STRATEGY.md usado
    
    @field_validator("edge")
    def edge_must_be_in_range(cls, v):
        if not (-1 <= v <= 1):
            raise ValueError("Edge fuera de rango")
        return v
```

### 5.2 `RiskVerdict` (Risk → Execution)
```python
from enum import Enum

class VerdictType(str, Enum):
    AUTO = "AUTO"
    REVIEW = "REVIEW"
    DISCARD = "DISCARD"

class RiskVerdict(BaseModel):
    opportunity: MarketOpportunity      # referencia al input
    verdict: VerdictType
    reasons: list[str]                  # razones en lenguaje natural
    kelly_fraction: Decimal             # fracción Kelly calculada
    recommended_size_usdc: Decimal      # tamaño recomendado
    blocking_rules: list[str]           # reglas que bloquearon (si DISCARD)
    qualitative_flags: list[str]        # QR-XXX que aplican
    evaluated_at: datetime
```

### 5.3 `ExecutionDecision` (Execution → Django App)
```python
class ExecutionDecision(BaseModel):
    verdict: RiskVerdict               # referencia al input
    order_type: str                    # "MARKET" | "LIMIT"
    limit_price: Decimal | None        # si es LIMIT
    size_usdc: Decimal                 # tamaño final
    polymarket_condition_id: str
    polymarket_token_id: str
    side: str                          # "BUY" | "SELL"
    
    # Estado para idempotencia en Django
    idempotency_key: str              # hash(condition_id + outcome + generated_at)
    requires_approval: bool           # True si verdict == REVIEW
    approval_deadline: datetime | None # para REVIEW: deadline antes del partido
    
    created_at: datetime
```

### 5.4 `AgentDecisionLog` (Django App — estado del agente)
```python
# Nuevo modelo en el Django App (extiende el spec anterior)
class AgentDecisionLog(models.Model):
    """Registro de todas las decisiones del agente. Fuente de idempotencia."""
    
    idempotency_key   = models.CharField(max_length=64, unique=True)
    
    # Contexto del torneo/deporte (extensible)
    tournament_id     = models.CharField(max_length=100)   # "fifa_world_cup_2026", "nfl_2026"
    sport             = models.CharField(max_length=50)    # "football", "american_football"
    strategy_id       = models.CharField(max_length=100)   # "match_winner_v1"
    strategy_version  = models.CharField(max_length=20)
    
    # Identificador Polymarket
    condition_id      = models.CharField(max_length=100)
    outcome           = models.CharField(max_length=10)
    
    # Resultado del pipeline
    verdict           = models.CharField(max_length=10)    # AUTO/REVIEW/DISCARD
    recommended_size  = models.DecimalField(max_digits=10, decimal_places=2)
    edge              = models.DecimalField(max_digits=6, decimal_places=4)
    
    # Estado de aprobación
    status            = models.CharField(max_length=20)
    # pending_approval | approved | rejected | executed | expired | discarded
    
    approved_by       = models.CharField(max_length=50, blank=True)  # "auto" | "human:{user}"
    approved_at       = models.DateTimeField(null=True)
    executed_at       = models.DateTimeField(null=True)
    
    # Snapshots completos para auditoría (fuente de verdad histórica)
    opportunity_json  = models.JSONField()    # MarketOpportunity serializado
    risk_verdict_json = models.JSONField()    # RiskVerdict serializado
    
    # Resultado — link al trade en el app de Polymarket Portfolio
    trade             = models.ForeignKey("Trade", null=True, on_delete=models.SET_NULL)
    
    created_at        = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["condition_id", "status"]),
            models.Index(fields=["tournament_id", "created_at"]),
            models.Index(fields=["created_at"]),
        ]
```

---

## 7. El Agente — `agent/CLAUDE.md`

Este archivo define cómo Claude opera el sistema. Es el equivalente al manual de trading del fondo.

```markdown
# CLAUDE.md — World Cup Trading Agent

## Rol
Eres el analista cuantitativo y operador de ejecución de este sistema de trading.
Tu trabajo es procesar oportunidades de mercado, aplicar las reglas de la estrategia
activa, y recomendar o ejecutar trades con reproducibilidad total.

## Reglas de operación

### 1. Antes de cualquier decisión, verifica idempotencia
Llama a `portfolio_tools.check_idempotency(condition_id, outcome)`.
Si ya existe un registro en estado != expired, NO proceses de nuevo — reporta el estado existente.

### 2. Lee siempre la estrategia activa antes de evaluar
La estrategia activa está en `strategies/world_cup_2026/STRATEGY.md`.
Nunca uses reglas de memoria — siempre re-lee el archivo.

### 3. Flujo para oportunidades nuevas
1. `research_tools.get_match_prediction(match_id)` → obtén probabilidades del modelo
2. `research_tools.get_market_price(condition_id, outcome)` → precio actual Polymarket
3. `research_tools.calculate_edge(model_prob, market_prob)` → edge
4. `risk_tools.evaluate(opportunity)` → RiskVerdict
5. Si verdict == DISCARD → log y para
6. Si verdict == AUTO → llama `execution_tools.build_order(verdict)` → ejecuta → log
7. Si verdict == REVIEW → genera reporte estructurado (ver template) → espera aprobación

### 4. Nunca improvises sizing
El tamaño siempre viene de `optimization_tools.calculate_size(verdict)`.
Nunca uses un número que no salga de esa función.

### 5. Formato de reporte REVIEW
Cuando un trade requiere aprobación, genera exactamente este formato:

---
TRADE REVIEW REQUEST
idempotency_key: {key}
deadline: {approval_deadline}

OPORTUNIDAD
  Partido: {home} vs {away}
  Mercado: {outcome}
  Fase: {tournament_phase}
  Kickoff: {kickoff_utc}

PROBABILIDADES
  Modelo: {model_probability:.1%}
  Polymarket: {market_probability:.1%}
  Edge: {edge:.1%}
  Confianza modelo: {model_confidence} (n={sample_size} partidos)

SIZING
  Kelly recomendado: {recommended_size_usdc} USDC
  Razón de REVIEW (no AUTO): {reasons}

FLAGS CUALITATIVOS
  {qualitative_flags}

RECOMENDACIÓN DEL AGENTE
  [Claude escribe aquí 2-3 líneas de análisis cualitativo]

ACCIONES
  [ ] APROBAR — responde "aprobar {idempotency_key}"
  [ ] RECHAZAR — responde "rechazar {idempotency_key} [razón]"
  [ ] MODIFICAR TAMAÑO — responde "modificar {idempotency_key} size={monto}"
---

## Lo que NO puedes hacer
- Modificar el STRATEGY.md directamente (solo el humano lo aprueba)
- Ejecutar un trade sin pasar por risk_tools.evaluate()
- Usar funciones de un área directamente sin pasar por agent/tools/
- Asumir que el estado del portafolio es el de la última vez que lo viste
```

---

## 8. Workflows Aprobados

Un workflow aprobado es un pipeline completo que Claude puede ejecutar en modo AUTO cuando las condiciones cuantitativas se cumplen.

### 7.1 `full_analysis.py` — Pipeline completo por evento

```python
"""
Workflow: Full Event Analysis
Status: approved
Trigger: manual o Celery task pre-evento
Input: event_id (str), tournament_id (str)
Output: lista de ExecutionDecision guardados en Django App
"""

def run(event_id: str, tournament_id: str):
    # Resuelve la estrategia activa para este torneo
    strategy = load_active_strategy(tournament_id)
    if not strategy:
        raise NoActiveStrategyError(f"No hay estrategia aprobada para {tournament_id}")
    
    # 1. Research — usa el adaptador del torneo, no importa el deporte
    prediction = research.get_event_prediction(event_id, tournament_id)
    opportunities = research.scan_polymarket_markets(prediction, strategy)
    
    # 2. Para cada oportunidad encontrada
    decisions = []
    for opp in opportunities:
        
        # Idempotencia — skip si ya fue procesado
        if portfolio.check_idempotency(opp.idempotency_key):
            continue
        
        # 3. Optimization
        opp_sized = optimization.calculate_edge_and_size(opp, strategy)
        
        # 4. Risk
        verdict = risk.evaluate(opp_sized, strategy)
        
        if verdict.verdict == VerdictType.DISCARD:
            portfolio.log_decision(verdict, status="discarded")
            continue
        
        # 5. Execution
        order = execution.build_order(verdict)
        decision = execution.classify(order, verdict)
        
        # 6. Guardar en Django App (sincronización bidireccional)
        log = portfolio.save_decision(decision)
        
        if decision.requires_approval:
            decisions.append({
                "mode": "REVIEW",
                "log_id": log.id,
                "report": editorial.build_review_report(decision)
            })
        else:
            result = execution.submit_order(order)
            portfolio.mark_executed(log, result)
            decisions.append({"mode": "AUTO", "log_id": log.id, "result": result})
    
    return decisions
```

### 7.2 `quick_scan.py` — Escaneo de oportunidades activas

```python
"""
Workflow: Quick Market Scan
Status: approved
Trigger: cada 30 minutos durante cualquier torneo activo
Input: ninguno (detecta torneos activos desde Django App)
Output: lista de MarketOpportunity ordenadas por edge desc
"""
def run():
    # Lee torneos activos desde Django App (tournaments con status=active)
    active_tournaments = django_client.get_active_tournaments()
    all_opportunities = []
    for t in active_tournaments:
        strategy = load_active_strategy(t.tournament_id)
        if not strategy:
            continue
        opps = research.scan_upcoming_events(t.tournament_id, hours_ahead=24)
        all_opportunities.extend(opps)
    # Ordena por edge descendente, filtra los ya procesados
    return sorted(all_opportunities, key=lambda o: o.edge, reverse=True)
```

### 7.3 `post_event_review.py` — Análisis post-evento

```python
"""
Workflow: Post Event Review
Status: approved
Trigger: manual después de que resuelve un mercado
Input: event_id, tournament_id
Output: PerformanceReport del evento
"""
def run(event_id: str, tournament_id: str):
    # Calcula PnL realizado del evento
    # Compara predicción del modelo vs resultado real
    # Identifica si el edge fue bien capturado
    # Genera reporte estructurado para Editorial
    # Escribe reporte en editorial/reports/{tournament_id}/{date}_{event_id}.md
```

---

## 9. Sistema de Skills — SKILL.md por Área

Cada área tiene un `SKILL.md` que Claude Code lee antes de operar dentro de ella. No es documentación para humanos — es el briefing técnico que el agente necesita para entender el contrato del área, qué puede hacer, qué no puede hacer, y cuándo invocarla.

### 8.1 Estructura canónica de un SKILL.md

```markdown
# SKILL: {Nombre del Área}

## ROL EN EL PIPELINE
[Una línea: qué produce esta área y a quién se lo entrega]

## CUÁNDO INVOCAR ESTA ÁREA
[Lista de triggers/condiciones — Claude lee esto para saber si esta área es relevante]

## CUÁNDO NO INVOCAR ESTA ÁREA
[Lista explícita de casos donde Claude NO debe usar esta área]

## FUNCIONES DISPONIBLES
[Tabla: función → qué hace → input schema → output schema]

## SCHEMAS QUE CONSUME
[Lista de schemas de entrada con su ubicación]

## SCHEMAS QUE PRODUCE
[Lista de schemas de salida con su ubicación]

## CONSTRAINTS Y REGLAS
[Lo que el agente nunca puede violar en esta área]

## EJEMPLOS DE USO
[1-2 ejemplos de cómo Claude invoca correctamente esta área]

## ERRORES COMUNES A EVITAR
[Antipatrones específicos de esta área]
```

### 8.2 `research/SKILL.md`

```markdown
# SKILL: Research

## ROL EN EL PIPELINE
Producir MarketOpportunity validadas con edge calculado.
Es la primera área del pipeline — nada se ejecuta sin pasar por aquí.

## CUÁNDO INVOCAR
- El humano dice "analiza el partido X" o "busca oportunidades para hoy"
- Se detecta un evento deportivo próximo en las siguientes 24h
- El humano pregunta "¿hay algo interesante en Polymarket?"
- Se inicia el workflow full_analysis o quick_scan

## CUÁNDO NO INVOCAR
- Para verificar el estado del portafolio (eso es portfolio/)
- Para construir una orden (eso es execution/)
- Para calcular PnL de trades ya ejecutados (eso es portfolio/)
- Si no hay torneo activo registrado en el Django App

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `model_loader.get_event_prediction()` | Carga probabilidades del modelo del torneo | event_id, tournament_id | MatchPrediction |
| `market_scanner.find_markets()` | Busca mercados en Polymarket para el evento | MatchPrediction, strategy | list[PolymarketMarket] |
| `edge_screener.calculate_edge()` | Calcula edge = p_modelo - p_polymarket | MatchPrediction, PolymarketMarket | MarketOpportunity |
| `probability_extractor.get_model_prob()` | Extrae probabilidad específica del outcome | MatchPrediction, outcome | Decimal |

## SCHEMAS QUE CONSUME
- `adapters/base.SportAdapter` (vía model_loader)
- CLOB API response (vía market_scanner → core/django_client)

## SCHEMAS QUE PRODUCE
- `research/schemas/match_prediction.MatchPrediction`
- `research/schemas/market_opportunity.MarketOpportunity`  ← este es el output principal

## CONSTRAINTS
- NUNCA hardcodear tournament_id — siempre leerlo del registro activo
- NUNCA calcular edge sin verificar primero que el mercado tiene volumen >= min_market_volume_usdc
- NUNCA producir una MarketOpportunity sin `generated_at` y `strategy_version`
- Si el modelo no tiene predicción para el evento, retornar None — no inventar probabilidad

## EJEMPLO DE USO
```python
# Correcto: pasar tournament_id explícito
prediction = model_loader.get_event_prediction("match_123", "fifa_world_cup_2026")
markets = market_scanner.find_markets(prediction, strategy)
opps = [edge_screener.calculate_edge(prediction, m) for m in markets]

# Incorrecto: asumir torneo
prediction = model_loader.get_event_prediction("match_123")  # ← falta tournament_id
```

## ERRORES COMUNES
- Confundir condition_id (identifica el market) con event_id (identifica el partido en el repo)
- Usar market_probability del último cache en vez de hacer el call live al CLOB API
- Generar MarketOpportunity con edge positivo cuando el volumen es < threshold (mercado ilíquido)
```

### 10.3 `risk/SKILL.md`

```markdown
# SKILL: Risk

## ROL EN EL PIPELINE
Recibe MarketOpportunity, aplica las reglas del STRATEGY.md activo,
y emite un RiskVerdict (AUTO / REVIEW / DISCARD) con sizing recomendado.
Es el guardián — nada llega a Execution sin pasar por aquí.

## CUÁNDO INVOCAR
- Siempre después de research/, antes de execution/
- El humano pregunta "¿es buena esta apuesta?" o "¿cuánto debo apostar?"
- Se necesita verificar si el portafolio tiene espacio para una posición nueva

## CUÁNDO NO INVOCAR
- Para analizar trades ya ejecutados (eso es portfolio/)
- Para construir la orden técnica (eso es execution/)
- Si no existe un MarketOpportunity validado de research/

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `kelly.fractional_kelly()` | Calcula tamaño óptimo fraccional | edge, bankroll, kelly_fraction | KellyOutput |
| `exposure.check_participant_exposure()` | Verifica límite de exposición por equipo | portfolio_state, participant, threshold | bool |
| `drawdown.check_portfolio_stop_loss()` | Verifica si el drawdown supera el límite | portfolio_state, max_drawdown | bool |
| `correlation.estimate_correlation()` | Estima correlación con posiciones abiertas | opportunity, open_positions | float |
| `evaluate()` | Función maestra: aplica todas las reglas del STRATEGY.md | MarketOpportunity, StrategyConfig, PortfolioState | RiskVerdict |

## SCHEMAS QUE CONSUME
- `research/schemas/market_opportunity.MarketOpportunity`
- `portfolio/schemas/portfolio_state.PortfolioState` (vía django_client)
- `strategies/{id}/STRATEGY.md` parseado como StrategyConfig

## SCHEMAS QUE PRODUCE
- `risk/schemas/risk_verdict.RiskVerdict`  ← output principal
- `risk/schemas/kelly_output.KellyOutput`

## CONSTRAINTS
- NUNCA emitir AUTO si alguna regla DISCARD aplica, aunque sea una sola
- NUNCA calcular Kelly sin leer primero el portfolio_state live del Django App
- NUNCA hardcodear thresholds — siempre leerlos del STRATEGY.md activo
- NUNCA emitir RiskVerdict sin listar las razones en el campo `reasons`
- Si hay flags cualitativos (QR-XXX), SIEMPRE incluirlos en `qualitative_flags` aunque no bloqueen

## ERRORES COMUNES
- Leer el portfolio_state de un cache stale — siempre hacer GET fresco al Django App
- Emitir REVIEW cuando todas las reglas AUTO se cumplen (ser demasiado conservador)
- No incluir los QR flags cuando aplican — el humano los necesita para tomar la decisión
```

### 10.4 `optimization/SKILL.md`

```markdown
# SKILL: Optimization

## ROL EN EL PIPELINE
Dado un RiskVerdict con Kelly calculado, refina el tamaño de la apuesta
aplicando constraints del portafolio completo (cvxpy). Garantiza que
el sizing sea óptimo en el contexto de todas las posiciones abiertas.

## CUÁNDO INVOCAR
- Después de risk/ cuando el verdict es AUTO o REVIEW
- El humano pregunta "¿cómo distribuyo el capital entre estas apuestas?"
- Se necesita optimizar un batch de oportunidades simultáneas

## CUÁNDO NO INVOCAR
- Antes de tener un RiskVerdict (no puede correr sin él)
- Si el verdict es DISCARD (no hay nada que optimizar)
- Para calibrar thresholds históricos (eso es threshold_calibrator, tarea separada)

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `bet_sizer.size_single()` | Sizing para una sola apuesta con Kelly fraccional | RiskVerdict, constraints | SizingOutput |
| `portfolio_optimizer.optimize_batch()` | cvxpy: max EV para un batch de oportunidades | list[RiskVerdict], PortfolioState | OptimizationResult |
| `threshold_calibrator.backtest_thresholds()` | Calibra edge_threshold_auto por backtesting | historical_trades, strategy | dict |

## SCHEMAS QUE CONSUME
- `risk/schemas/risk_verdict.RiskVerdict`
- `portfolio/schemas/portfolio_state.PortfolioState`

## SCHEMAS QUE PRODUCE
- `optimization/schemas/sizing_output.SizingOutput`
- `optimization/schemas/optimization_result.OptimizationResult`

## CONSTRAINTS
- El sizing NUNCA puede superar max_bet_usdc del STRATEGY.md
- El sizing NUNCA puede ser menor a min_bet_usdc (si es así, retornar SKIP)
- NUNCA modificar el verdict (AUTO/REVIEW/DISCARD) — solo el tamaño
- Si cvxpy no converge, usar Kelly fraccional simple como fallback
```

### 10.5 `execution/SKILL.md`

```markdown
# SKILL: Execution

## ROL EN EL PIPELINE
Convierte un SizingOutput en una orden real de Polymarket.
Valida el precio live, estima slippage, construye el payload del CLOB API,
y clasifica si la orden procede en AUTO o necesita REVIEW final.

## CUÁNDO INVOCAR
- Después de optimization/, cuando hay un SizingOutput válido
- El humano dice "ejecuta" o "procede con la apuesta"
- Un trade REVIEW fue aprobado por el humano en el Django App

## CUÁNDO NO INVOCAR
- Sin pasar por risk/ y optimization/ primero (sin excepciones)
- Si el precio live ha movido más de X% vs el precio en la señal (re-evaluar desde research/)
- Si el mercado está a < min_hours_to_event del kickoff

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `price_validator.validate_live_price()` | Verifica que el precio live sea aceptable | token_id, signal_price, tolerance | bool |
| `slippage_estimator.estimate()` | Estima slippage dado el orderbook actual | token_id, size_usdc | SlippageEstimate |
| `order_builder.build()` | Construye el payload para el CLOB API | SizingOutput, live_price | TradeOrder |
| `order_classifier.classify()` | Decide AUTO vs REVIEW para la ejecución final | TradeOrder, RiskVerdict | ExecutionDecision |
| `submit_order()` | Envía la orden al CLOB API de Polymarket | TradeOrder | OrderResult |

## SCHEMAS QUE CONSUME
- `optimization/schemas/sizing_output.SizingOutput`
- `risk/schemas/risk_verdict.RiskVerdict`

## SCHEMAS QUE PRODUCE
- `execution/schemas/trade_order.TradeOrder`
- `execution/schemas/execution_decision.ExecutionDecision`  ← output principal
- `execution/schemas/order_result.OrderResult`

## CONSTRAINTS
- NUNCA llamar submit_order() si ExecutionDecision.requires_approval == True
- NUNCA hardcodear credenciales de Polymarket — siempre de variables de entorno
- Si price_validator falla, NO re-intentar automáticamente — reportar al humano
- SIEMPRE guardar el OrderResult en el Django App antes de retornar (via django_client)
- La idempotency_key DEBE verificarse contra el Django App antes de submit_order()

## ERRORES COMUNES
- Llamar submit_order() en modo REVIEW (el error más costoso del sistema)
- No verificar idempotencia antes de enviar la orden (puede resultar en posición doble)
- Usar el precio de la señal en vez del precio live para construir la orden LIMIT
```

### 10.6 `portfolio/SKILL.md`

```markdown
# SKILL: Portfolio

## ROL EN EL PIPELINE
Es el puente entre el repo de trading y el Django App.
Lee estado del portafolio, persiste decisiones del agente,
y calcula métricas de performance. Es el área más conectada al Django App.

## CUÁNDO INVOCAR
- Siempre al inicio del pipeline (para leer portfolio_state)
- Para verificar idempotencia antes de procesar cualquier oportunidad
- Para persistir el resultado de cada etapa del pipeline
- El humano pregunta "¿cómo voy?" o "¿cuál es mi PnL?"

## CUÁNDO NO INVOCAR
- Para construir órdenes (eso es execution/)
- Para generar reportes narrativos (eso es editorial/)

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `position_tracker.get_state()` | Lee estado completo del portafolio del Django App | — | PortfolioState |
| `position_tracker.get_exposure()` | Exposición por participante del torneo activo | tournament_id | dict |
| `pnl_calculator.realized_pnl()` | PnL realizado acumulado | list[Trade] | Decimal |
| `pnl_calculator.unrealized_pnl()` | PnL no realizado de posiciones abiertas | list[Position], prices | Decimal |
| `performance_metrics.summary()` | Métricas completas de performance | PortfolioState | PerformanceSummary |
| `check_idempotency()` | Verifica si una key ya existe en AgentDecisionLog | idempotency_key | AgentDecisionLog \| None |
| `save_decision()` | Persiste un AgentDecisionLog en Django App | ExecutionDecision | AgentDecisionLog |
| `mark_executed()` | Marca un log como ejecutado | idempotency_key, OrderResult | AgentDecisionLog |

## SCHEMAS QUE CONSUME
- `execution/schemas/execution_decision.ExecutionDecision`
- `execution/schemas/order_result.OrderResult`

## SCHEMAS QUE PRODUCE
- `portfolio/schemas/portfolio_state.PortfolioState`  ← consumido por risk/ y optimization/
- `portfolio/schemas/performance_summary.PerformanceSummary`

## CONSTRAINTS
- NUNCA cachear PortfolioState entre steps del pipeline — siempre hacer GET fresco
- NUNCA escribir directamente a la DB — siempre a través de django_client
- check_idempotency() es OBLIGATORIO antes de save_decision() — no hay excepciones
- Si el Django App está caído, el workflow PARA — no continúa con estado stale

## ERRORES COMUNES
- Leer portfolio_state una sola vez y usarlo para todo el pipeline (puede quedar stale)
- No hacer check_idempotency() por "estar seguros de que es nueva" — siempre verificar
```

### 8.7 `editorial/SKILL.md`

```markdown
# SKILL: Editorial

## ROL EN EL PIPELINE
Última área del pipeline. Convierte datos estructurados de las otras áreas
en reportes legibles: resúmenes de análisis, narrativas de trades, y digests
de performance. NO toma decisiones de trading.

## CUÁNDO INVOCAR
- Para generar el reporte de un REVIEW que espera aprobación
- Después de que resuelve un mercado (post_event_review workflow)
- El humano pide "dame un resumen de la semana" o "¿cómo estuvo el torneo?"
- Después de un batch de ejecuciones para documentar lo que pasó

## CUÁNDO NO INVOCAR
- En el camino crítico de una ejecución urgente (primero ejecuta, luego reporta)
- Para tomar decisiones de trading (solo narra, no decide)

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `report_builder.build_review_report()` | Reporte estructurado para un REVIEW pendiente | ExecutionDecision | str (Markdown) |
| `report_builder.build_execution_summary()` | Resumen de una ejecución completada | OrderResult, RiskVerdict | str (Markdown) |
| `trade_narrator.narrate()` | Claude redacta narrativa cualitativa de un trade | Trade, context | str |
| `performance_digest.weekly()` | Digest semanal completo | tournament_id, period | WeeklyDigest |
| `performance_digest.tournament_final()` | Reporte final del torneo | tournament_id | WeeklyDigest |

## SCHEMAS QUE CONSUME
- `execution/schemas/execution_decision.ExecutionDecision`
- `execution/schemas/order_result.OrderResult`
- `portfolio/schemas/performance_summary.PerformanceSummary`

## SCHEMAS QUE PRODUCE
- `editorial/schemas/trade_report.TradeReport`
- `editorial/schemas/weekly_digest.WeeklyDigest`
- Archivos Markdown en `editorial/reports/{tournament_id}/`

## CONSTRAINTS
- NUNCA publicar automáticamente — todo queda en editorial/reports/ para revisión manual
- Los reportes son SIEMPRE en Markdown, guardados con fecha en el nombre
- NUNCA incluir credenciales, wallet addresses completas, o claves privadas en reportes
- La narrativa de trade_narrator debe indicar si fue AUTO o REVIEW (y por qué)

## ERRORES COMUNES
- Generar el reporte REVIEW antes de que risk/ haya calculado el kelly_fraction
- Omitir los qualitative_flags del RiskVerdict en el reporte (el humano los necesita)
- Guardar el reporte sin tournament_id en el path (rompe la organización por torneo)
```

---

## 10. Sistema de Hooks — `agent/HOOKS.md`

Los hooks son los triggers que Claude Code escucha para saber qué área invocar. No son eventos automáticos — Claude Code se lanza manualmente, pero al recibir un input, mapea la intención del humano al hook correspondiente y ejecuta el área correcta.

### 9.1 `agent/HOOKS.md` — Registro Canónico

```markdown
# HOOKS.md — Registro de Triggers del Agente

## QUÉ ES UN HOOK
Un hook es la condición de entrada que determina qué workflow o área
debe activarse dado el input del operador. Claude Code los lee para
mapear lenguaje natural a acciones del sistema.

## TABLA DE HOOKS

| Hook ID | Trigger (lenguaje natural) | Área/Workflow | Modo |
|---|---|---|---|
| H-001 | "analiza el partido X" / "evalúa el evento X" | full_analysis workflow | PIPELINE |
| H-002 | "busca oportunidades" / "¿qué hay para hoy?" | quick_scan workflow | PIPELINE |
| H-003 | "nuevo torneo: {id}" / "registra el torneo X" | portfolio/ → django_client | WRITE |
| H-004 | "¿cómo voy?" / "dame el PnL" / "estado del portafolio" | portfolio/ → performance_metrics | READ |
| H-005 | "post-partido" / "revisa el resultado de X" | post_event_review workflow | PIPELINE |
| H-006 | "aprobar {key}" | portfolio/ → django_client.mark_approved() | WRITE |
| H-007 | "rechazar {key} [razón]" | portfolio/ → django_client.mark_rejected() | WRITE |
| H-008 | "modificar {key} size={monto}" | portfolio/ → django_client + re-run execution/ | WRITE |
| H-009 | "resumen de la semana" / "digest semanal" | editorial/ → performance_digest.weekly() | READ |
| H-010 | "calibra los thresholds" | optimization/ → threshold_calibrator.backtest() | COMPUTE |
| H-011 | "nueva estrategia para {torneo}" | research/notebooks/ → draft mode | DRAFT |
| H-012 | "¿qué estrategia está activa?" | tournaments/registry.py → READ | READ |

## MODOS DE EJECUCIÓN

**PIPELINE:** Corre el flujo completo Research → Risk → Optimization → Execution → Portfolio
- Lee el SKILL.md de cada área antes de invocarla
- Verifica idempotencia en portfolio/ al inicio
- Termina en Editorial si hay algo que reportar

**READ:** Solo lectura — consulta el Django App o los archivos del repo
- No escribe estado
- No llama a Polymarket
- Responde inmediatamente

**WRITE:** Escribe estado en el Django App
- Siempre confirma con el humano antes si el write es irreversible
- Retorna el estado actualizado después de escribir

**COMPUTE:** Corre cálculos pesados (backtesting, optimización)
- Puede tomar tiempo — informa al humano del progreso
- No escribe a producción sin aprobación

**DRAFT:** Modo experimental — Claude escribe código o estrategias nuevas
- Todo va a notebooks/ o a strategies con status: draft
- NUNCA activa workflows aprobados en modo DRAFT

## REGLAS DE MAPEO

1. Si el input contiene un event_id o nombre de partido → H-001 (full_analysis)
2. Si el input es una pregunta sobre el estado → H-004 (portfolio read)
3. Si el input contiene "aprobar/rechazar/modificar" + una key → H-006/H-007/H-008
4. Si el input menciona "torneo" + "nuevo/registra" → H-003
5. Si ningún hook mapea claramente → Claude pregunta al humano antes de actuar
6. Si hay ambigüedad entre H-001 y H-002 → preferir H-002 (menos destructivo)

## HOOK CHAINS (secuencias automáticas)

Algunos hooks activan otros automáticamente:

H-001 → si hay REVIEW pendiente → Editorial genera reporte de REVIEW
H-006 (aprobar) → execution/ → submit_order() → H-005 (post_event al resolver)
H-005 → Editorial → guarda reporte en editorial/reports/{tournament_id}/

## REGLA DE ORO
Claude Code NUNCA ejecuta un hook WRITE o PIPELINE sin leer primero:
1. agent/CLAUDE.md (reglas de operación generales)
2. El SKILL.md del área que va a invocar
3. El STRATEGY.md activo del torneo en curso
```

### 9.2 Flujo de decisión de Claude Code al recibir un input

```
Input del humano
      │
      ▼
¿Mapea a algún Hook?
      │
   sí │                    no
      ▼                    ▼
Lee HOOKS.md          Claude pregunta al humano
Identifica Hook ID    "No entiendo qué area
      │                activar — ¿puedes ser
      ▼                más específico?"
¿Es PIPELINE/WRITE?
      │
   sí │                   no (READ/COMPUTE)
      ▼                   ▼
Lee CLAUDE.md global  Ejecuta directamente
Lee SKILL.md del área
Lee STRATEGY.md activo
      │
      ▼
¿Hay idempotency conflict?
      │
   sí │           no
      ▼           ▼
Reporta estado  Ejecuta área
existente       correspondiente
                      │
                      ▼
               ¿Hay resultado para Editorial?
                      │
                   sí │
                      ▼
               Lee editorial/SKILL.md
               Genera reporte
               Guarda en reports/{tournament_id}/
```

---

## 11. Integración Django App ↔ Repo de Trading

Este es el puente crítico del sistema. El repo de trading es el cerebro (modelos, funciones, lógica); el Django App es la memoria (estado, historial, wallet). Están desacoplados por diseño pero se sincronizan en tiempo real a través de una API interna.

### 10.1 Principio de Separación

```
REPO DE TRADING                          DJANGO APP
(sports-quant-trading/)            (polymarket-portfolio/)
─────────────────────              ──────────────────────
Lógica pura, sin estado    ←──►    Estado persistente
Modelos deportivos                 Historial de wallet
Schemas Pydantic                   Modelos Django/PostgreSQL
Funciones testeables               API REST interna
Claude opera aquí                  UI de aprobación aquí
```

El repo **nunca escribe directamente a la base de datos**. Siempre habla con el Django App a través de HTTP. Esto garantiza que hay un único punto de verdad del estado y que el Django App puede validar antes de persistir.

### 10.2 `core/django_client.py` — Cliente HTTP del Repo

```python
"""
Cliente HTTP para comunicación repo → Django App.
Todas las operaciones que necesitan estado pasan por aquí.
"""
import os
import requests
from decimal import Decimal
from datetime import datetime

DJANGO_API_BASE = os.getenv("DJANGO_API_BASE", "http://localhost:8000/api/agent")
DJANGO_API_KEY  = os.getenv("DJANGO_API_KEY")   # token interno, no es auth de usuario

class DjangoClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token {DJANGO_API_KEY}",
            "Content-Type": "application/json",
        })
    
    # ── LECTURA DE ESTADO ─────────────────────────────────────────────────
    
    def get_portfolio_state(self) -> dict:
        """Estado actual: posiciones abiertas, bankroll, drawdown."""
        return self._get("/portfolio/state/")
    
    def get_active_tournaments(self) -> list[dict]:
        """Torneos registrados con status=active en el Django App."""
        return self._get("/tournaments/active/")
    
    def check_idempotency(self, idempotency_key: str) -> dict | None:
        """Retorna el DecisionLog existente o None si es nuevo."""
        try:
            return self._get(f"/decisions/{idempotency_key}/")
        except NotFoundError:
            return None
    
    def get_open_positions(self, tournament_id: str = None) -> list[dict]:
        """Posiciones abiertas, opcionalmente filtradas por torneo."""
        params = {"tournament_id": tournament_id} if tournament_id else {}
        return self._get("/positions/open/", params=params)
    
    def get_exposure_by_participant(self, tournament_id: str) -> dict:
        """Exposición por equipo/jugador — para el constraint de risk."""
        return self._get(f"/tournaments/{tournament_id}/exposure/")
    
    # ── ESCRITURA DE ESTADO ───────────────────────────────────────────────
    
    def save_decision(self, decision_payload: dict) -> dict:
        """
        Persiste un AgentDecisionLog nuevo.
        El Django App valida idempotency_key antes de insertar.
        Retorna el log creado con su id.
        """
        return self._post("/decisions/", decision_payload)
    
    def mark_executed(self, idempotency_key: str, order_result: dict) -> dict:
        """Actualiza status=executed y linkea el Trade resultante."""
        return self._patch(f"/decisions/{idempotency_key}/execute/", order_result)
    
    def mark_approved(self, idempotency_key: str, approved_by: str = "human") -> dict:
        """Marca un REVIEW como aprobado. El Django App valida que esté pending."""
        return self._patch(f"/decisions/{idempotency_key}/approve/", {"approved_by": approved_by})
    
    def mark_rejected(self, idempotency_key: str, reason: str) -> dict:
        """Rechaza un REVIEW."""
        return self._patch(f"/decisions/{idempotency_key}/reject/", {"reason": reason})
    
    def register_tournament(self, tournament_config: dict) -> dict:
        """Registra un torneo nuevo en el Django App."""
        return self._post("/tournaments/", tournament_config)
    
    # ── SYNC DE WALLET ────────────────────────────────────────────────────
    
    def trigger_wallet_sync(self) -> dict:
        """Dispara el sync de la wallet de Polymarket (Celery task en Django)."""
        return self._post("/sync/trigger/", {})
    
    def get_trade_by_condition(self, condition_id: str, outcome: str) -> dict | None:
        """Busca un trade ejecutado por condition_id + outcome."""
        try:
            return self._get(f"/trades/", params={"condition_id": condition_id, "outcome": outcome})
        except NotFoundError:
            return None
```

### 10.3 API Interna del Django App — Endpoints `/api/agent/`

Estos endpoints solo son accesibles con el `DJANGO_API_KEY` interno (token de servicio, no de usuario).

```
# Estado del portafolio
GET  /api/agent/portfolio/state/              → bankroll, drawdown_7d, total_open_positions
GET  /api/agent/positions/open/               → lista de Position (filtrable por tournament_id)
GET  /api/agent/tournaments/{id}/exposure/    → {participant: exposure_pct}

# Torneos
GET  /api/agent/tournaments/active/           → lista de TournamentConfig activos
POST /api/agent/tournaments/                  → registrar torneo nuevo

# Decisiones del agente
GET  /api/agent/decisions/{key}/              → DecisionLog por idempotency_key
POST /api/agent/decisions/                    → crear nuevo DecisionLog
PATCH /api/agent/decisions/{key}/execute/     → marcar como ejecutado
PATCH /api/agent/decisions/{key}/approve/     → aprobar (REVIEW → approved)
PATCH /api/agent/decisions/{key}/reject/      → rechazar

# Sync
POST /api/agent/sync/trigger/                 → dispara Celery task de wallet sync
GET  /api/agent/sync/status/                  → status del último sync

# Trades (lectura)
GET  /api/agent/trades/                       → trades filtrados (condition_id, outcome, status)
```

### 10.4 `TournamentConfig` — Modelo Django para torneos

```python
class TournamentConfig(models.Model):
    """
    Registro de torneos en el Django App.
    El repo lo crea, el Django App lo persiste y lo expone al agente.
    """
    tournament_id     = models.CharField(max_length=100, unique=True)
    # ej: "fifa_world_cup_2026", "nfl_2026", "nba_playoffs_2027"
    
    display_name      = models.CharField(max_length=200)
    sport             = models.CharField(max_length=50)
    status            = models.CharField(max_length=20, default="draft")
    # draft | active | completed | archived
    
    start_date        = models.DateField()
    end_date          = models.DateField()
    
    active_strategy   = models.CharField(max_length=200, blank=True)
    # path relativo al STRATEGY.md activo, ej: "fifa_world_cup_2026/strategies/match_winner_v1"
    
    # Constraints de riesgo globales para este torneo
    max_exposure_pct  = models.DecimalField(max_digits=5, decimal_places=2, default=15.0)
    max_open_positions = models.IntegerField(default=10)
    
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)
```

### 10.5 Flujo de Sincronización — Diagrama Completo

```
REPO (Claude opera aquí)                      DJANGO APP (UI aquí)
═══════════════════════                       ═══════════════════

1. Claude llama full_analysis(event_id)
   │
   ├─► django_client.get_portfolio_state()  ──► GET /api/agent/portfolio/state/
   │   ◄─────────────────────────────────────── {bankroll, drawdown, positions}
   │
   ├─► django_client.check_idempotency(key) ──► GET /api/agent/decisions/{key}/
   │   ◄─────────────────────────────────────── None (no existe → continuar)
   │
   ├─► [pipeline Research → Risk → Execution]
   │
   ├─► django_client.save_decision(payload) ──► POST /api/agent/decisions/
   │   ◄─────────────────────────────────────── {id, idempotency_key, status}
   │
   ├── Si AUTO:
   │   ├─► execution.submit_order()          ──► Polymarket CLOB API
   │   └─► django_client.mark_executed(key)  ──► PATCH /api/agent/decisions/{key}/execute/
   │       ◄──────────────────────────────────── Django linkea Trade al DecisionLog
   │
   └── Si REVIEW:
       └─► Claude muestra reporte al humano
           │
           Humano ve /agent/pending/ en Django App UI
           Humano aprueba → POST /agent/approve/{key}/
           │
           Django cambia status → approved
           │
           Claude (o Celery task) detecta aprobación
           ├─► execution.submit_order()
           └─► django_client.mark_executed(key)

SYNC CONTINUO (Celery Beat en Django):
  ● Cada 2 min: update_live_prices() → actualiza Position.current_price
  ● Cada 15 min: sync_portfolio() → reconcilia con Polymarket Data API
  ● Cada hora: check_expired_reviews() → marca como expired los REVIEW vencidos
```

### 10.6 Variables de Entorno — Conexión Repo ↔ Django

```env
# En el repo de trading (.env)
DJANGO_API_BASE=http://localhost:8000      # local dev
# DJANGO_API_BASE=https://portfolio.tudominio.com  # producción
DJANGO_API_KEY=secret-internal-token-aqui

# En el Django App (.env, además de lo ya definido en el SPEC anterior)
AGENT_API_KEY=secret-internal-token-aqui  # mismo token, validado en DRF TokenAuth
REPO_PATH=/path/to/sports-quant-trading   # para que Celery pueda importar funciones del repo
```

---

## 12. Extensión del Django App — Nuevas Pantallas

El Django App del Polymarket Portfolio SPEC se extiende con un módulo `/agent/`:

### Nuevos modelos
- `AgentDecisionLog` — definido en sección 5.4
- `TournamentConfig` — definido en sección 8.4
- `WorkflowRun` — registro de cada ejecución de workflow (inicio, fin, decisiones generadas, errores)

### Nuevas URLs
```
/agent/                          → Dashboard del agente
/agent/pending/                  → Trades REVIEW pendientes de aprobación
/agent/approve/<key>/            → POST: aprobar
/agent/reject/<key>/             → POST: rechazar con razón
/agent/log/                      → Historial completo de decisiones
/agent/log/?tournament=nfl_2026  → Filtrado por torneo
/agent/performance/              → Métricas del agente
/agent/tournaments/              → Gestión de torneos registrados
```

### Pantalla principal del agente (`/agent/`)

```
┌─────────────────────────────────────────────────────────────────┐
│  AGENT STATUS                              ● LIVE — FIFA WC 2026│
├─────────────────────────────────────────────────────────────────┤
│  ACTIVE TOURNAMENT                                              │
│  FIFA World Cup 2026  │  Strategy: match_winner_v1  │  approved │
├─────────────────────────────────────────────────────────────────┤
│  PENDING REVIEW (2)                                             │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Argentina vs France  │  YES  │  Edge: +9.2%  │  4h left  │ │
│  │ Strategy: match_winner_v1  │  Confidence: MEDIUM  n=8     │ │
│  │ Size: $35 USDC  │  Kelly: 4.8%                           │ │
│  │ Flags: QR-002 (lesión reportada Mbappé)                   │ │
│  │                                                           │ │
│  │ [✓ APROBAR]  [✗ RECHAZAR]  [≈ MODIFICAR TAMAÑO]          │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  AUTO EXECUTED TODAY (5)              DISCARDED TODAY (12)      │
│  Spain YES $25  ✓  Germany NO $15 ✓  Edge < 4%: 9  │ SL: 3    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. Cómo Agregar un Deporte Nuevo (ej: NFL 2026)

El sistema es extensible por diseño. Agregar la NFL significa 4 pasos, sin tocar el pipeline de áreas:

**Paso 1 — Crear el adaptador** en `adapters/american_football/`
```python
# adapters/american_football/elo_loader.py
from adapters.base import SportAdapter

class NFLEloAdapter(SportAdapter):
    def get_event_prediction(self, event_id: str) -> dict:
        # conecta con el repo NFL cuando exista
        ...
```

**Paso 2 — Registrar el torneo** en `tournaments/registry.py`
```python
TOURNAMENTS = {
    "fifa_world_cup_2026": TournamentConfig(
        sport="football",
        adapter=FootballEloAdapter,
        ...
    ),
    "nfl_2026": TournamentConfig(           # ← agregar esto
        sport="american_football",
        adapter=NFLEloAdapter,
        ...
    ),
}
```

**Paso 3 — Crear la carpeta del torneo** en `tournaments/nfl_2026/`
- `TOURNAMENT.md` — metadata
- `adapter.py` — config específica
- `strategies/game_winner_v1/STRATEGY.md` con `status: draft`

**Paso 4 — Registrar en el Django App**
```python
django_client.register_tournament({
    "tournament_id": "nfl_2026",
    "display_name": "NFL 2026 Season",
    "sport": "american_football",
    "status": "draft",
    "start_date": "2026-09-06",
    "end_date": "2027-02-08",
})
```

El pipeline Research → Risk → Optimization → Execution → Portfolio → Editorial no cambia. Solo cambia el adaptador que alimenta Research.

---

## 14. Cómo Claude Escribe Código Nuevo (Protocolo de Contribución)

Durante un torneo, Claude puede escribir nuevas funciones de research (estrategias experimentales). El protocolo es estricto para evitar que código no revisado llegue a AUTO:

1. **Draft en `research/notebooks/`** — no entra al pipeline, solo exploratorio
2. **Formaliza en `research/functions/`** con su schema en `research/schemas/`
3. **Crea estrategia en `tournaments/{id}/strategies/_draft/`** con `status: draft`
4. **Escribe tests** en `tests/unit/research/`
5. **El humano revisa** y cambia `status: draft → under_review → approved`
6. Solo cuando `status: approved` puede un workflow usarlo en modo AUTO

Esto garantiza que código experimental de Claude nunca llega a producción sin revisión.

---

## 15. Editorial — Reporte Estructurado

El área editorial genera reportes internos en Markdown/JSON. No publica automáticamente.

### `WeeklyDigest` (schema)
```python
class WeeklyDigest(BaseModel):
    period_start: datetime
    period_end: datetime
    
    # Performance
    total_bets: int
    auto_bets: int
    review_bets: int
    approved_reviews: int
    rejected_reviews: int
    discarded: int
    
    pnl_realized: Decimal
    pnl_unrealized: Decimal
    win_rate: float
    roi: float
    
    # Edge analysis
    avg_edge_at_entry: Decimal
    avg_edge_captured: Decimal     # edge real vs edge predicho
    edge_accuracy: float           # % veces que edge > 0 fue correcto
    
    # Best/worst
    best_trade: TradeReport
    worst_trade: TradeReport
    
    # Narrativa generada por Claude
    performance_narrative: str     # párrafo de análisis
    lessons_learned: list[str]     # bullets
    next_week_outlook: str
```

El reporte se guarda en `editorial/reports/{tournament_id}/YYYY-MM-DD_digest.md` dentro del repo.
Desde ahí el operador decide qué partes publicar y en qué canal.

---

## 16. Fases de Implementación

### Fase 1 — Estructura base (1 día)
- Crear repo con estructura completa de directorios
- `core/types.py`, `core/exceptions.py`, `core/django_client.py`
- `adapters/base.py` (SportAdapter ABC)
- Todos los schemas Pydantic de las 6 áreas
- `tournaments/registry.py` + `tournaments/fifa_world_cup_2026/` completo
- `agent/CLAUDE.md` completo

### Fase 2 — Research + Risk (2 días)
- `adapters/football/` — conectar con modelos Elo/Bayes/TrueSkill del repo existente
- `research/functions/`: model_loader, market_scanner, edge_screener
- `risk/functions/`: kelly, exposure, drawdown
- Tests unitarios para todas las funciones
- Primera estrategia `match_winner_v1/STRATEGY.md` → status: under_review

### Fase 3 — Optimization + Execution (1 día)
- `optimization/functions/bet_sizer.py` con cvxpy
- `execution/functions/order_builder.py` + Polymarket CLOB auth
- `execution/functions/order_classifier.py` (AUTO vs REVIEW logic)
- `agent/tools/` wrappers de todas las áreas

### Fase 4 — Integración Django App (1 día)
- `TournamentConfig` y `AgentDecisionLog` models en Django
- API interna `/api/agent/` con DRF (todos los endpoints de sección 8.3)
- Vistas `/agent/` con HTMX (pending, approve, reject)
- `agent/workflows/full_analysis.py` completo con django_client integrado

### Fase 5 — Editorial + Activación (1 día)
- `editorial/functions/report_builder.py` y `performance_digest.py`
- `agent/workflows/quick_scan.py` y `post_event_review.py`
- `match_winner_v1/STRATEGY.md` → status: approved
- E2E test con evento real del torneo activo

---

## 17. Principios Anti-Deuda Técnica

**Nunca rompas el contrato de schemas.** Si un schema necesita cambiar, crea v2 del schema y migra. No modifiques in-place schemas que ya usan workflows aprobados.

**Functions son funciones puras.** Si una función necesita estado o llamada a API, no va en `functions/` — va en `agent/tools/` o en `core/django_client.py` como cliente HTTP.

**El STRATEGY.md es la única fuente de reglas.** Ningún threshold vive en código Python hardcodeado. Si el threshold no está en el STRATEGY.md activo, no existe.

**Idempotency key en todo.** `hash(condition_id + outcome + strategy_id + strategy_version + date)`. Si la key ya existe en `AgentDecisionLog` del Django App, el workflow para silenciosamente.

**Todo lo que Claude genera tiene `generated_at`, `tournament_id` y `strategy_version`.** Nunca hay una decisión sin contexto de qué torneo y qué estrategia la produjo.

**El Django App es la única fuente de estado.** El repo no tiene base de datos propia, no escribe archivos de estado locales, no cachea posiciones. Si necesita saber el estado del portafolio, pregunta al Django App.
