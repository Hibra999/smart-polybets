# 2026-07-14 — Liga MX: historia, calibración de localía y backtest (conclusión: SIN edge vs cierre)

## Datos
- **Fuente**: football-data.co.uk (`new/MEX.csv`), 4,655 partidos de Liga MX desde 2012
  con cuotas de cierre (Pinnacle/B365/promedio). Descargada a
  `data/liga_mx_2026/ingest/MEX.csv`; refresh con `curl` (URL en el script de ingesta).
- **Ingesta** (`load_history_fdcouk.py`, idempotente): 336 partidos 2025/26 →
  `historical_match` (Poisson); replay Elo 2023/24→2025/26 → seeds en `team.elo_rating`.
- **Mazatlán/Atlante**: Mazatlán jugó hasta el Clausura 2026; Atlante lo reemplaza en el
  Apertura 2026 y **NO hereda su historia** (clubes distintos) → arranca 1500/media de liga.

## A. Calibración de localía (grid search, Brier con score 1/0.5/0)
Replay Elo k=40 sobre 2022/23→2025/26 (burn-in: 2022/23):
| home_adv | 0 | 40 | 60 | **80** | 100 | 120 |
|---|---|---|---|---|---|---|
| Brier | .17035 | .16217 | .16013 | **.15940** | .15989 | .16150 |
→ `TournamentConfig.home_adv_elo = 80.0` (antes 65 placeholder). El Poisson estima
`home_factor = 1.40` con la 2025/26 — la localía en Liga MX es fuerte y real.

## A2. Torneos cortos: la TABLA se reinicia, la fuerza se regresa (no se resetea)
Pregunta del CIO (2026-07-14): "Apertura y Clausura son 2 torneos distintos, cada uno
inicia de 0 — ¿lo manejaste así?". Respuesta empírica (grid sobre 2022/23-2025/26):
| ρ (regresión a la media en cada frontera A/C) | 1.00 continuo | 0.85 | **0.80** | 0.70 | 0.50 |
|---|---|---|---|---|---|
| Brier | .15940 | .15856 | **.15856** | .15890 | .16056 |
- **Reset total sería incorrecto** (ρ chico empeora); **continuo puro también es
  subóptimo**. Óptimo conjunto: `home_adv=80, ρ=0.80` (adv=80 se mantiene).
- Aplicado en `load_history_fdcouk.py`: regresión en cada frontera del replay **más una
  regresión final** (Clausura 2026 → Apertura 2026, mercado de verano). Seeds quedan:
  Cruz Azul 1638 … Puebla 1374 (comprimidos vs el replay continuo).
- Estructura ya respetada de antes: `liga_mx_2026` = **solo el Apertura 2026** (el
  Clausura 2027 será otro tournament_id), liguilla como phase propia, warmup por torneo.
- Poisson: `historical_match` agrupa Apertura 2025 + Clausura 2026 a propósito — las
  tasas de ataque/defensa son fuerza (no tabla) y 17 partidos/equipo por torneo corto
  es muestra flaca; el shrinkage (k=5) amortigua el drift de plantel.

## B. Calidad de modelos en 2025/26 — CONDICIONES DE PRODUCCIÓN (2ª corrida, 2026-07-14)
Pedido del CIO: simular como opera el pipeline — **warmup de 3 fechas** por equipo y
por torneo corto (55 partidos excluidos → 281 evaluados) y **regresión del 20%**
(ρ=0.80) en cada frontera Apertura/Clausura, también dentro del backtest.
| Métrica | Modelo | Mercado (cierre) |
|---|---|---|
| Elo Brier binario (1/0.5/0) | 0.15507 | **0.15049** |
| Poisson 1X2 Brier 3-clases | 0.19934 | **0.19516** |
| Poisson 1X2 log-loss | 1.0018 | **0.9820** |

**El mercado de cierre sigue ganando en todas las métricas** (el warmup mejora al
modelo, pero el mercado mejora igual en el mismo subset — la brecha no se cierra).
(1ª corrida sin warmup/ρ para referencia: Elo .15783/.15142, Poisson .19843/.19391.)

## C. Simulación de apuestas (Poisson 1X2 vs cierre, ¼ Kelly, max $25; warmup 3 + ρ=0.80)
| Umbral EV | Apuestas | ROI/staked | Max DD |
|---|---|---|---|
| ≥0.02 | 179 | **-4.5%** | 36% |
| ≥0.05 | 163 | **-4.4%** | 36% |
| ≥0.10 | 130 | **-1.7%** | 31% |
| ≥0.15 | 100 | **-0.7%** | 25% |

⚠️ El "+0.6%" de EV≥0.15 de la 1ª corrida **se volvió -0.7% con warmup**: era ruido
concentrado en las fechas tempranas. Con condiciones de producción NO hay ningún
umbral rentable — el veredicto "sin edge vs cierre" queda reforzado.

## Conclusión (para la decisión de aprobar la estrategia)
1. **El modelo solo NO tiene edge contra precios eficientes** (cierre de Pinnacle/avg).
   Los "edges" del Poisson vs cierre son mayormente ilusorios → ROI negativo.
2. Si va a haber edge en Liga MX será porque **Polymarket precia peor que el cierre**
   (liquidez baja, mercado nuevo — recién abrió los markets el 2026-07-13). Eso NO está
   demostrado: hay que medirlo.
3. **Recomendación**: `match_winner_ligamx_v1` sigue en **draft**. Durante J1-J3 correr en
   modo observación: registrar precio de PM vs Poisson vs cierre (el CSV se actualiza
   semanalmente) y recién con evidencia de que PM es blando, proponer aprobación con
   umbral de edge alto (≥0.10) y sizing chico.
4. El backtest es reproducible: `python scripts/ligamx_backtest.py` (sin red, lee el CSV).
5. **Reporte HTML**: `editorial/reports/liga_mx_2026/ligamx-backtest.html`, regenerable con
   `python scripts/ligamx_backtest_html.py` (recomputa todo, no hay números pegados).

## D. Experimento ML multiclase (propuesta del CIO, 2026-07-14)
¿Un Random Forest H/D/A sobre nuestros features (Elo+localía, TrueSkill μ/σ,
lambdas y probs Poisson — 16 features walk-forward, sin lookahead) mejora las
cosas? `scripts/ligamx_ml_experiment.py` (train 2023/24-2024/25 tras burn-in,
test 2025/26, n=336):
| Modelo | log-loss | Brier3 |
|---|---|---|
| Poisson 1X2 | 1.0054 | 0.20028 |
| Random Forest (500 árboles, calibrado isotónico) | 1.0083 | 0.19895 |
| Logística multinomial (mismos features) | 0.9914-0.9949 | ~0.1980 |
| **Mercado (cierre devig)** | **0.9748-0.9774** | **0.1936-0.1939** |
| Logística mercado+features (info incremental) | 0.9746-0.9810 | — |

Conclusiones:
1. **Multiclase sí ayuda, pero no vía RF**: con 680 partidos de train el RF apenas
   empata al Poisson; una logística multinomial simple le gana a ambos (~1% de
   log-loss sobre Poisson). Si se adopta stacking, que sea logístico (o GBM cuando
   haya 10+ temporadas de features).
2. **Test decisivo de edge**: nuestros features agregan **cero información
   incremental sobre el precio de cierre** (Δlogloss +0.0002 sin escalar /
   -0.0061 escalado — cero o negativo). El mercado ya contiene todo lo que
   nuestros features saben, más lo que no tenemos (alineaciones, noticias, flujo).
3. Implicación: invertir en "modelar mejor" con ESTOS features tiene techo — el
   camino de edge sigue siendo microestructura/venue blando (ver finding
   2026-07-14-ligamx-sesgos-mercado.md). Features que sí podrían mover la aguja:
   xG, alineaciones/rotación, descanso/viaje — justo lo que el cierre ya precia.

## Estado del modelo tras la ingesta (verificado)
- Poisson J1: base 1.45, home_factor 1.40, 18 equipos ajustados (Atlante = media, LOW).
- Seeds Elo: Cruz Azul 1695 (campeón Clausura) … Puebla 1310. Adapter aplica +80 de localía.
