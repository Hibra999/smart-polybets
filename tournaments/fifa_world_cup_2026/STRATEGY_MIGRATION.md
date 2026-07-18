# Migración: `pypro_worldcup_betting` → diseño agéntico

Este documento mapea la estrategia y los modelos del repo `pypro_worldcup_betting`
al framework agéntico de `pypro_polymarket_agent`.

## Qué se migró

La **estrategia activa** del laboratorio (`worldcup.db`, tabla `strategy`):

> **"kelly + blend + filtro no"** — `sizing=kelly`, `kelly_fraction=0.25`,
> `side_criterion=blend` (Elo+Bayes 50/50), `use_bayes_filter=False`,
> `start_match_no=2`, `odds=1.5`. Backtest: **yield 21.8% / ROI 19.0%**.

Más los **modelos** que la alimentan (Elo + Bayes) y los **datos** del Mundial 2026.

## Mapeo de componentes

| Origen (`pypro_worldcup_betting`) | Destino (`pypro_polymarket_agent`) |
|---|---|
| `app/src/elo.py` (`expected_score`, `EloSystem`, `margin_multiplier`) | `adapters/football/wc_models.py` (portado, puro) |
| `app/src/bayes.py` (`elo_to_prior`, `BetaBelief`, `BayesianLeague`) | `adapters/football/wc_models.py` (portado, puro) |
| `app/src/fifa_seed.py` (`fifa_to_elo`) | `adapters/football/wc_models.py` |
| `app/src/pipeline.py` (`Pipeline`, `match_log`, `prematch_rec`) | `adapters/football/wc_pipeline.py` (`WorldCupPipeline`) |
| `app/src/trueskill_model.py` (lib `trueskill`) | `adapters/football/wc_trueskill.py` — **port puro 1v1** (sin dependencia), validado contra la lib a 1e-5 |
| `app/src/odds.py` + tabla `Odds` (Polymarket/Codere) | `scripts/migrate_worldcup_data.py` → tabla `polymarket_odds` + `research/functions/odds_source.SqliteOddsSource` |
| `app/src/betting.py` (`pick_side`, `BetParams`) | `research/functions/wc_strategy.py` (`pick_side`, `build_worldcup_opportunity`) |
| `app/src/betting.py` (`stake_amount` Kelly) | `risk/functions/kelly.py` (Kelly fraccional del framework) |
| `Strategy` activa en DB | `tournaments/.../strategies/match_winner_wc_v1/STRATEGY.md` |
| `worldcup.db` (tournament 2026) | `data/fifa_world_cup_2026/fifa_world_cup_2026.sqlite` vía `scripts/migrate_worldcup_data.py` |
| `Pipeline.seed(fifa_to_elo(fifa_points))` | semilla directa desde `team.elo_rating` (= `elo_seed` del origen) |

## Mapeo de parámetros (`BetParams` → `StrategyConfig`)

| BetParams | StrategyConfig | Valor migrado |
|---|---|---|
| `side_criterion` | `side_criterion` | `blend` |
| `blend_weight` | `blend_weight` | `0.5` |
| `sizing` = `kelly` | `sizing_method` | `fractional_kelly` |
| `kelly_fraction` | `kelly_fraction` | `0.25` |
| `start_match_no` | `warmup_match_no` | `2` |
| `use_bayes_filter` | `use_bayes_filter` | `false` |
| `bayes_threshold` | `bayes_threshold` | `0.5` |
| `odds` (constante) | — | viene del precio live de Polymarket (no se fija) |
| `bankroll0` | — | viene del estado del portafolio (`LocalState`) |

## Cómo se traduce la lógica de decisión

1. **Selección de lado** (`pick_side`): idéntica. Usa los componentes Elo/Bayes
   del `MatchPrediction` (campo nuevo `components`) y `side_criterion`. El blend
   compara `w·elo + (1-w)·bayes` por lado. El `p_pick` para el sizing es la prob
   **Elo** del lado elegido (igual que el origen).
2. **Warmup** (`start_match_no`): el campo `appearances` del `MatchPrediction`
   (nº de aparición de cada lado) permite saltar la 1ª aparición.
3. **Filtro Bayes**: si `use_bayes_filter`, descarta si la media Bayes del lado
   elegido < umbral.
4. **Sizing Kelly**: el Kelly del framework usa `price = market_probability`, así
   que `b = (1-price)/price = odds - 1`. Es la **misma** fórmula Kelly del origen.

## Diferencias deliberadas (envoltura agéntica)

El origen es un motor de backtest/recomendación; el framework añade gobernanza:

- **AUTO/REVIEW/DISCARD**: el origen siempre recomienda. Aquí, el `RiskVerdict`
  marca REVIEW en fases de knockout, confianza LOW, o flags cualitativos (QR-xxx).
  El gate cuantitativo se calibró para imitar al origen: `edge_threshold_discard=0`
  (sólo descarta edge negativo, donde el Kelly daría 0 igual).
- **Idempotencia + estado**: bankroll y posiciones vienen de `LocalState` (no de una
  constante), y cada decisión lleva `idempotency_key` + `strategy_version`.
- **Mercado binario**: outcomes `[HOME_WIN, AWAY_WIN]` (el modelo es win/no-win;
  no hay apuesta al empate), mapeado a los mercados "Will X win" de Polymarket.
- **Sin ventaja de localía**: el adapter worldcup NO añade home advantage (torneo
  neutral), fiel al `expected_score` del origen.

## Cómo correrlo

```bash
# 1. Migrar los datos reales del Mundial 2026
python scripts/migrate_worldcup_data.py

# 2. La estrategia activa ya es la migrada (registry → match_winner_wc_v1)
python -c "from tournaments.registry import load_active_strategy; \
print(load_active_strategy('fifa_world_cup_2026').strategy_id)"

# 3. Tests (incluye los de migración)
pytest -q
```

## Modelos disponibles (los 4 criterios funcionan)

- **elo / bayes / blend**: portados puros en `wc_models.py` (la estrategia activa usa `blend`).
- **trueskill**: portado puro en `wc_trueskill.py` (1v1 con empates nativos), validado
  numéricamente contra la librería `trueskill` del origen. El criterio `trueskill` ya
  usa probabilidades TrueSkill reales (no fallback a Elo).

## Cuotas (wired)

`scripts/migrate_worldcup_data.py` migra las 404 cuotas (Polymarket + Codere) a la
tabla `polymarket_odds`. `SqliteOddsSource` las expone como `PolymarketMarket` por
lado para `research`. Ejemplo real (Argentina vs Austria): modelo Elo 0.818 vs
mercado Polymarket 0.615 → **edge +20%**.

## Pendiente (no bloquea la estrategia)

- **CLOB API live**: `SqliteOddsSource` usa las cuotas migradas (probabilidades reales
  pero sin volumen ni condition_id/token_id reales — placeholders). El reemplazo live
  consulta Polymarket en tiempo real con la misma interfaz (`market_source`).
