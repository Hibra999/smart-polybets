# DATA_SOURCES — fifa_world_cup_2026

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
