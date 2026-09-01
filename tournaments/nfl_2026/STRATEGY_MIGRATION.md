# Migración: `sports_bet` (NFL) → diseño agéntico

Mapea el modelo y la estrategia del repo `sports_bet` (apuestas NFL) al framework
agéntico compartido por Liga MX y NFL.

## Qué se migró

El **modelo TrueSkill** de `sports_bet/code/analysis_true_skill.py` (rating por
win/loss con la librería `trueskill`, elige el equipo de mayor μ) + el sizing
**Kelly** de `test_bet_sizing.py`.

## Mapeo de componentes

| Origen (`sports_bet`) | Destino (PEPA) |
|---|---|
| `analysis_true_skill.py` (lib `trueskill`, `rate_1vs1`) | `adapters/football/trueskill.py` (port puro 1v1, reutilizado) |
| pipeline de ratings (procesa juegos en orden) | `adapters/american_football/nfl_pipeline.py` (`NFLPipeline`) |
| `select_winner` (compara μ) | `research/functions/strategy_selection.pick_side` (criterio `trueskill`) |
| `kelly_criterion` (`test_bet_sizing.py`) | `risk/functions/kelly.fractional_kelly` |
| EV multi-apuesta (scipy SLSQP) | `optimization/portfolio_optimizer` (cvxpy, opcional) |
| odds Codere (moneyline americano) | precio implícito de Polymarket (research) |
| datos NFL (nfl.com scrape + Postgres) | **nflverse `games.csv`** → `scripts/migrate_nfl_data.py` |

## Decisiones del port

- **Modelo**: NFL usa **solo TrueSkill** (no Elo/Bayes). El origen elegía el equipo
  de mayor μ; aquí se usa la **probabilidad de victoria** TrueSkill
  `P = Φ((μ_A−μ_B)/√(2β²+σ²))` para poder medir edge vs el mercado.
- **Sin empates**: `draw_probability=0.0` (los empates NFL son <0.5%).
- **Margen ignorado**: TrueSkill actualiza por win/loss, no por marcador (igual que el origen).
- **Semilla**: fresh `N(25, 8.3)` para todos; los ratings se construyen procesando
  2022-2025 (1139 juegos) en orden cronológico.

## Datos (nflverse)

`scripts/migrate_nfl_data.py` baja `games.csv` de nflverse y puebla
`data/nfl_2026/nfl_2026.sqlite`:
- **2022-2025**: 1139 juegos `finished` (siembran TrueSkill).
- **2026**: 272 juegos `scheduled` (los que el adapter predice).

## Validación

Backtest temporada **2025 regular**: el pick "mayor TrueSkill" acertó
**168/271 = 62.0%** de los juegos (sólo ratings, sin spread ni stats).

## Estrategia

`tournaments/nfl_2026/strategies/game_winner_v1/STRATEGY.md` (approved, activa):
`side_criterion=trueskill`, mercado binario `[HOME_WIN, AWAY_WIN]`, Kelly fraccional
(¼), warmup de 4 juegos, REVIEW en playoffs.

## Pendiente / realidad

- **La temporada NFL 2026 arranca el 6-sep-2026**: hoy no hay juegos 2026 jugados ni
  mercados de Polymarket NFL. El sistema queda armado y backtesteado; el trading live
  arranca en septiembre (mismo pipeline + `PolymarketLiveSource` con el tag NFL).
- **No migrado**: el 2º modelo de `sports_bet` (clasificador ML por stats off/def).
  Quedó fuera de alcance; se puede agregar como criterio alternativo más adelante.
