# TOURNAMENT: NFL 2026 Season

tournament_id: nfl_2026
sport: american_football
status: active
start_date: 2026-09-06
end_date: 2027-02-08

## Descripción
Temporada regular NFL 2026 + playoffs. 32 franquicias, 18 semanas + postemporada.

## Fuente de datos
- SQLite: `data/nfl_2026/nfl_2026.sqlite`
- Ver `data/nfl_2026/DATA_SOURCES.md`.

## Modelo
- Adapter activo: `adapters/american_football/trueskill_loader.AmericanFootballTrueSkillAdapter`
  (TrueSkill evolutivo, **migrado de `sports_bet`**). Backtest 2025: 62.0% de aciertos.
- `AmericanFootballEloAdapter` (Elo) queda como alternativa.
- Mercado binario (sin empate práctico).

## Datos
- SQLite poblado desde nflverse con `python scripts/migrate_nfl_data.py`
  (historia 2010-2025 + calendario 2026). La estrategia activa filtra desde 2022.

## Estrategias
| strategy_id | market_type | status | nota |
|---|---|---|---|
| game_winner_v1 | game_winner | **approved (activa)** | migrada de sports_bet (TrueSkill + Kelly) |

Ver `STRATEGY_MIGRATION.md`. La estrategia aprobada sigue en dry-run salvo una
autorización live explícita.
