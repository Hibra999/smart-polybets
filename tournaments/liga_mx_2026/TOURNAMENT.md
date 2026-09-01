# TOURNAMENT: Liga MX — Apertura 2026

tournament_id: liga_mx_2026
sport: football
status: active (modo observación — ninguna estrategia approved)
start_date: 2026-07-16
end_date: 2026-12-13

## Descripción
Torneo Apertura 2026 de la Liga MX (México). **18 equipos**, 17 jornadas de fase
regular + liguilla (play-in + cuartos + semis + final, ida y vuelta). Hay
**ventaja de localía real** y el torneo es largo.
Nota de plantel 2026: **Atlante FC está en la liga** (no Mazatlán) — verificado en
el mercado de campeón de Polymarket (evento 701237).

## Fuente de datos
- SQLite: `data/liga_mx_2026/liga_mx_2026.sqlite` (DDL canónico football)
- Ingesta: `data/liga_mx_2026/ingest/fetch_fixtures_pm.py` (Polymarket SDK vía
  `venue/discovery`, tag Liga MX = **102448**; idempotente, corre a diario).
  Polymarket lista los partidos en ventana rodante (~2 jornadas); el calendario
  se completa incrementalmente. Ver `data/liga_mx_2026/DATA_SOURCES.md`.
- Historia + cuotas de cierre: football-data.co.uk (`ingest/load_history_fdcouk.py`).
- Ticks de mercado en tiempo real (jornadas): `scripts/record_market_ticks.py`
  → `market_ticks.sqlite` (precios + book depth + score live, 1/min).
- Operación del theta trade: `docs/theta-trade-manual.md`.

## Modelo — CALIBRADO con historia real (2026-07-14)
- **Elo con localía calibrada**: `home_adv_elo = 80` (grid search Brier sobre
  2022/23-2025/26, ver `scripts/ligamx_backtest.py`). Seeds desde replay
  2023/24→2025/26 de football-data **con regresión ρ=0.80 a la media en cada
  frontera Apertura/Clausura** (los torneos cortos reinician la tabla, no la
  fuerza — reset total empeora el Brier, continuo puro también; calibrado):
  Cruz Azul 1638 … Puebla 1374. **Atlante = 1500** (reemplaza a Mazatlán, no
  hereda historia). El torneo registrado es SOLO el Apertura 2026; el Clausura
  2027 será otro tournament_id.
- **Poisson con localía**: `neutral_venue=False`; con la 2025/26 en
  `historical_match` estima `home_factor = 1.40` y base 1.45 goles/equipo
  (`scripts/poisson_predictions.py --tournament liga_mx_2026`).
- **Bayes/TrueSkill sin localía**: son señales de fuerza relativa, no de precio.
  Con seeds reales ya no arrancan flat (se siembran del Elo).
- **Resultados**: `scripts/update_results.py --tournament liga_mx_2026 --apply`
  (Exact Score de PM; fallback escalera O/U — `venue/results.py`).

## ⚠️ Backtest 2025/26 (finding 2026-07-14-ligamx-backtest): SIN edge vs cierre
El mercado de cierre (Pinnacle/avg) le gana a Elo y Poisson en Brier/log-loss, y la
simulación de apuestas da ROI negativo salvo umbrales extremos. **La estrategia queda
en draft**: el edge, si existe, debe venir de que Polymarket precia peor que el cierre
(mercado nuevo, liquidez baja). Plan J1-J3: modo observación registrando PM vs Poisson
vs cierre; aprobar solo con evidencia de PM blando (umbral edge ≥0.10, sizing chico).

## Estrategias
| strategy_id | market_type | status | nota |
|---|---|---|---|
| match_winner_ligamx_v1 | match_winner | **draft (NO operar)** | backtest: sin edge vs cierre (finding 2026-07-14-ligamx-backtest) |
| theta_lay_v1 | match_winner (trading NO del favorito) | **draft — validación J1-J3** | ejecución manual vía CLI; manual: `docs/theta-trade-manual.md` |

El pipeline no apuesta este torneo hasta que el CIO apruebe la estrategia
(status: approved). Mientras tanto, `scan_market`/`propose_bet` sirven en modo
observación.
