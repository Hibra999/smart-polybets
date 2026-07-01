# DATA_SOURCES — nfl_2026

## Estado de datos
| Tabla | Fuente actual | Cobertura | Frecuencia actualización | Script de ingesta |
|---|---|---|---|---|
| tournament | Manual | 100% | Una vez | — |
| team | Manual / nflverse | 100% | Una vez | fetch_rosters.py |
| player | nflverse rosters | 95% | Semanal | fetch_rosters.py |
| week / fixture | ESPN / nflverse schedule | 100% | Semanal | fetch_schedule.py |
| match_team_stat | nflverse | Post-partido | Por partido | fetch_game_stats.py |
| match_player_stat | nflverse | Post-partido | Por partido | fetch_game_stats.py |
| injury_report | NFL injury report (jueves) | 100% | Semanal | fetch_rosters.py |
| elo_rating_history | Calculado localmente | 100% | Post-partido | calculado por el modelo |

## Fuentes pendientes de confirmar
- Líneas de Vegas (spread/total/moneyline): evaluar The Odds API
- snap counts: nflverse participation data

## Cómo actualizar antes de un partido
1. `python data/nfl_2026/ingest/fetch_schedule.py` — actualiza el calendario
2. `python data/nfl_2026/ingest/fetch_rosters.py` — rosters + injury report (sale jueves)
3. Verificar status de QBs titulares en `injury_report` (activa QR-201)

## Notas
- El injury report del jueves es mandatorio en NFL — siempre revisar antes de operar
- Los ratings Elo se calculan post-partido por los modelos del repo
