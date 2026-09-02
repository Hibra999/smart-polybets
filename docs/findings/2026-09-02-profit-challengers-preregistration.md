# Preregistro de challengers de rentabilidad

**Congelado:** 2026-09-02, antes de ejecutar estos challengers sobre sus ventanas de
evaluación.

**Estado:** investigación; no modifica estrategias activas, no autoriza live y no
promete rentabilidad futura.

## Motivo

El backtest canónico usa una probabilidad binaria en Liga MX aunque `match_winner`
liquida empate como pérdida. Eso sobrestima `HOME_WIN` y `AWAY_WIN`. En NFL, el
challenger de ratings y EPA ya perdió contra el moneyline. Las dos pruebas siguientes
atacan esas causas concretas sin agregar un modelo grande ni barrer thresholds.

![Pipeline SOTA de validación y decisión](../assets/sota-validation-pipeline.png)

## Reglas comunes congeladas

- Replay estrictamente temporal: cada pronóstico sólo usa temporadas anteriores.
- Bankroll inicial: 1,000 USDC; Kelly 1/4; apuesta mínima 5 y máxima 25 USDC.
- Se ejecuta un solo lado por partido: el de mayor valor esperado neto positivo.
- Slippage adverso fijo: el precio implícito sube 0.01 antes de calcular payout.
- Fee histórico: 500 bps con la fórmula binaria del repositorio sobre el precio
  ejecutado. La cuota fuente ya contiene el margen del bookmaker.
- No hay búsqueda de threshold: se apuesta sólo cuando el valor esperado queda
  positivo después de slippage y fee.
- Se reportan apuestas, profit, ROI sobre bankroll, yield sobre stake, drawdown y
  resultado por temporada. Un agregado positivo que dependa de un solo año falla.
- La prueba se ejecuta una vez. Un fallo no habilita variantes sobre las mismas
  ventanas.

## LMX-MKT-1X2-01 — precio calibrado y mejor cierre

**Hipótesis.** Una probabilidad 1X2 derivada del consenso, corregida por
favourite-longshot bias, evita el error binario del flujo actual; la dispersión entre
books puede dejar valor en el mejor precio publicado.

**Datos.** `MEX.csv`: `AvgCH/AvgCD/AvgCA` forman el consenso y
`MaxCH/MaxCD/MaxCA` son el proxy de precio ejecutable. No se sustituyen datos faltantes.

**Modelo.** Para cada temporada objetivo se ajusta un único parámetro `beta > 0` por
log-loss multiclase sobre todas las temporadas anteriores:

`p_i = (1 / AvgC_i)^beta / sum_j((1 / AvgC_j)^beta)`.

Se usa `scipy.optimize.minimize_scalar` con límites fijos `[0.5, 2.0]`. En cada partido
se compara `p_i` con `MaxC_i`, después de costos, y se toma como máximo una posición.

**Evaluación prequential.** Temporadas 2022/23, 2023/24, 2024/25 y 2025/26. Cada fold
se entrena sólo con fechas anteriores al inicio de su temporada.

**Límite de interpretación.** `MaxC` demuestra como mucho una hipótesis de
line-shopping en datos de bookmaker. No equivale a un fill histórico de Polymarket y
no puede promover la estrategia sin libros T-24h del venue.

## NFL-SPREAD-ML-01 — consistencia spread/moneyline

**Hipótesis.** El closing spread contiene una estimación independiente de la
probabilidad de victoria. Una discrepancia suficientemente grande entre esa estimación
y el moneyline puede sobrevivir margen y costos. La relación entre spread y victoria
está documentada, pero la evidencia sobre ineficiencia NFL es mixta y los sesgos pueden
desaparecer con el tiempo.

**Datos.** `fixture.spread_home`, `moneyline_home`, `moneyline_away` y resultado final,
sólo temporada regular y sin empates.

**Modelo.** Regresión logística sin regularización práctica (`C=1_000`) con una sola
feature, `spread_home`, y outcome `home_win`. Para cada temporada objetivo se ajusta
con todas las temporadas anteriores disponibles desde 2010. No usa ratings, EPA,
resultado previo ni el moneyline como feature.

**Evaluación prequential.** Temporadas 2022, 2023, 2024 y 2025. La probabilidad del
spread se contrasta con ambos closing moneylines y se aplica exactamente la regla de
costos y staking común.

## Criterio de éxito y promoción

El objetivo de backtest exige simultáneamente, en **cada deporte**, profit, ROI y yield
agregados mayores que cero después de costos, al menos tres de cuatro temporadas
rentables y al menos 100 apuestas. También se publica bootstrap por partido del yield;
si su IC 95% toca cero, el resultado se etiqueta exploratorio aunque el PnL puntual
sea positivo.

Esto no basta para promover una estrategia. Se mantienen los gates existentes de
calibración, comparación contra `market-only`, al menos 300 decisiones, estabilidad y
fills reales. Liga MX continúa `draft`; NFL continúa dry-run.

## Evidencia que motivó la prueba

- Dixon y Coles modelan explícitamente H/D/A y la dependencia de marcadores bajos;
  una probabilidad binaria no es un sustituto válido para ese mercado:
  https://doi.org/10.1111/1467-9876.00065
- El favourite-longshot bias y el margen pueden distorsionar la conversión directa de
  cuotas en probabilidades: https://doi.org/10.1111/1467-8586.00174
- El spread NFL es un predictor significativo de victoria, aunque la literatura no
  encuentra rentabilidad estable en todos los periodos:
  https://doi.org/10.1177/1527002507311726 y
  https://doi.org/10.1080/00036840500368904
- Los sesgos NFL sólo importan económicamente si sobreviven costos de transacción:
  https://doi.org/10.1016/0304-405X(91)90034-H

## Registro de intentos

Este documento registra dos nuevas hipótesis: `LMX-MKT-1X2-01` y
`NFL-SPREAD-ML-01`. Se suman a los intentos ya publicados (Dixon-Coles, ML Liga MX,
ratings+EPA NFL, TrueSkill y Platt Polymarket); no los reemplazan ni ocultan.
