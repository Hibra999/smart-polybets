# DATA_SOURCES — liga_mx_2026 (Apertura 2026)

## Estado de datos
| Tabla | Fuente actual | Cobertura | Frecuencia | Script de ingesta |
|---|---|---|---|---|
| tournament | Manual (ingest) | 100% | Una vez | fetch_fixtures_pm.py |
| phase | Manual (regular/liguilla) | 100% | Una vez | fetch_fixtures_pm.py |
| team | **Polymarket** (mercado campeón, evento 701237) | 18/18 | Una vez | fetch_fixtures_pm.py |
| fixture | **Polymarket** (tag 102448, ventana rodante ~2 jornadas) | J1+J2 al 2026-07-14 | **DIARIA** | fetch_fixtures_pm.py |
| resultado (goles) | **Polymarket Exact Score** (fallback: escalera O/U) | por partido | post-partido | `scripts/update_results.py --tournament liga_mx_2026 --apply` |
| elo_rating | **Replay Elo 2023/24-2025/26** (football-data, home_adv=80) | 17/18 (atlante=1500) | pre-torneo | load_history_fdcouk.py |
| historical_match | **football-data.co.uk MEX.csv** (2025/26, 336 partidos) | 100% | semanal (CSV se actualiza) | load_history_fdcouk.py |
| player / availability | — | 0% | — | PENDIENTE |

## Decisiones y gotchas
- **Todo por el SDK de Polymarket** (regla de oro #7): equipos y calendario salen de los
  mercados, no de scrapers. Tag Liga MX = **102448** (slug `mex`); Apertura = 105620.
- **Ventana rodante**: PM solo lista ~2 jornadas hacia adelante → correr la ingesta a
  diario o el fixture de un mercado cerrado queda huérfano.
- Cada partido aparece como ~6 eventos en PM (principal + "more markets"); la ingesta
  filtra por `has_winner_market=True` y dedupea por (home, away, fecha).
- **Atlante FC está en la liga 2026** (no Mazatlán) — verificado en el mercado campeón.
- **Historia + seeds cargados (2026-07-14)**: football-data.co.uk `new/MEX.csv` (descarga
  directa, sin scraping; la regla anti-scraper es solo para Polymarket). Refresh semanal:
  `curl -sL -o data/liga_mx_2026/ingest/MEX.csv https://www.football-data.co.uk/new/MEX.csv`
  y re-correr `load_history_fdcouk.py --apply` (idempotente). El CSV trae cuotas de CIERRE
  (Pinnacle/avg) → sirve para medir si Polymarket es blando (ver finding
  2026-07-14-ligamx-backtest).
- **Atlante sin historia**: reemplaza a Mazatlán (Apertura 2026) y no hereda su Elo/goles
  — arranca en 1500/media de liga con confianza LOW.
- Los kickoffs se guardan en UTC (regla #8). Horarios raros tipo `01:07` vienen así de PM.

| ticks de mercado | **Recorder por minuto** (bid/ask/spread/vol + book en ventana activa + score live) | mercados winner/draw abiertos | 1/min mientras corra | `scripts/record_market_ticks.py` → `market_ticks.sqlite` (gitignored, WAL) |
| snapshots Polymarket | Ask, top-3, profundidad, fee y decisión pública | Próxima fecha disponible | Diario | `generate_reports.py --live --snapshot-dir data` → `ingest/market_snapshots.csv` |
| minutos de gol + rojas | **ESPN scoreboard API** (`mex.1`, sin key; "Santos" = Santos Laguna) | 2025/26: 322 partidos, 999 goles, 138 rojas | por temporada (extensible --from/--to) | `ingest/fetch_goal_minutes_espn.py` → tabla `match_timeline_event` |

## Cómo actualizar (rutina diaria de temporada)
1. `python data/liga_mx_2026/ingest/fetch_fixtures_pm.py --apply` — jornadas nuevas + kickoffs
2. `python scripts/update_results.py --tournament liga_mx_2026 --apply` — finaliza jugados
3. Verificar: 0 fixtures con kickoff pasado en `scheduled`
4. **Días de jornada**: dejar corriendo `python scripts/record_market_ticks.py` en una
   terminal dedicada (1 snapshot/min; book depth automático de -60min a +150min del
   kickoff). Es el insumo del análisis del theta trade (finding 2026-07-14-theta-trade).
5. **Post-jornada**: exportar cada evento a su carpeta versionable
   (`python scripts/export_event_ticks.py --tournament liga_mx_2026 --all`) →
   `data/liga_mx_2026/events/<fecha>-<evento>/ticks.sqlite` (ticks + capturas finas +
   sesiones + meta). El buffer rodante sigue gitignored; los exports SÍ se commitean.
