# TOURNAMENT: FIFA World Cup 2026

tournament_id: fifa_world_cup_2026
sport: football
status: active
start_date: 2026-06-11
end_date: 2026-07-19

## Descripción
Copa del Mundo 2026 (USA/Canadá/México). 48 equipos, fase de grupos + knockout.
Sedes en tres países; muchos partidos en venue neutral.

## Fuente de datos
- SQLite: `data/fifa_world_cup_2026/fifa_world_cup_2026.sqlite`
- Ver `data/fifa_world_cup_2026/DATA_SOURCES.md`.

## Modelo
- Adapter activo: `adapters/football/worldcup_adapter.FootballWorldCupAdapter`
  (pipeline Elo+Bayes evolutivo, **migrado de `pypro_worldcup_betting`**).
- `FootballEloAdapter` (Elo simple) queda disponible como alternativa.
- TrueSkill: no portado; el criterio `trueskill` degrada a Elo.

## Datos
- SQLite poblado desde `worldcup.db` con `python scripts/migrate_worldcup_data.py`
  (100 partidos del Mundial 2026, 28 jugados).

## Estrategias
| strategy_id | market_type | status | nota |
|---|---|---|---|
| match_winner_wc_v1 | match_winner | **approved (activa)** | migrada de worldcup (blend+Kelly) |
| match_winner_v1 | match_winner | approved | genérica 3-way (HOME/DRAW/AWAY) |
| top_scorer_v1 | top_scorer | draft | |

Ver `STRATEGY_MIGRATION.md` para el mapeo origen → framework.
