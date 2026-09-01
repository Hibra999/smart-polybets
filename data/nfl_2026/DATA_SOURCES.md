# DATA_SOURCES — nfl_2026

## Estado de datos
| Tabla | Fuente actual | Cobertura | Frecuencia actualización | Script de ingesta |
|---|---|---|---|---|
| tournament | Manual | 100% | Una vez | — |
| team | Manual / nflverse | 100% | Una vez | fetch_rosters.py |
| player | nflverse weekly rosters + depth charts | Plantel publicado | Semanal | fetch_rosters.py |
| week / fixture | nflverse games | 100% | Diario | fetch_schedule.py |
| match_team_stat | nflverse play-by-play | EPA, success, explosivas, pass rate y PROE | Por partido | fetch_game_stats.py |
| match_player_stat | Sin fuente conectada | 0% | — | — |
| injury_report | Sin asset nflverse 2026 | 0%; se registra `partial`, sin imputar | Jueves | — |
| elo_rating_history | Calculado localmente | 100% | Post-partido | calculado por el modelo |

## Fuentes pendientes
- Líneas de Vegas (spread/total/moneyline): evaluar The Odds API
- snap counts: nflverse participation data
- Injury report vigente: conectar una fuente oficial con licencia y timestamp auditable

## Cómo actualizar antes de un partido
1. `python data/nfl_2026/ingest/fetch_schedule.py --since 2022` — reconstruye DB y calendario
2. `python data/nfl_2026/ingest/fetch_game_stats.py --since 2022 --through 2026`
3. `python data/nfl_2026/ingest/fetch_rosters.py --season 2026`
4. Verificar externamente el injury report y QB titular antes de operar; la DB no lo tiene aún

## Notas
- La ausencia de injury report debe bloquear una decisión live sensible a QB; nunca se rellena
- `fetch_game_stats.py` es idempotente por `(fixture_id, team_id)`
- si nflverse aún no publicó el play-by-play del año actual, lo registra como `partial`
  y conserva los años disponibles; un `404` de un año histórico sigue siendo fatal
- Los ratings Elo se calculan post-partido por los modelos del repo
