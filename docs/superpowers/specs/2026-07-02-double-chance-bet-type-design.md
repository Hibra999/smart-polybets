# Modo de apuesta "doble-oportunidad" (rival no gana) — Diseño

**Fecha:** 2026-07-02
**Estado:** aprobado (pendiente de plan de implementación)

## Objetivo

Añadir un modo de apuesta seleccionable por estrategia — `bet_type: double_chance` —
que, en vez de apostar el pick del modelo a GANAR, apueste al **rival del pick a NO
ganar**: la doble-oportunidad 1X (el pick gana **o** empata en el tiempo reglamentario
de 90'). El edge y el sizing se calculan con el modelo Poisson, que sí modela empates.

## Motivación

El backtest leak-free sobre 80 partidos del Mundial mostró que la doble-oportunidad
supera claramente a "el pick gana": ROI **+4.8%** vs **−1.1%**, capturando 11–16 empates
que la apuesta al ganador pierde. Confirmamos con datos reales (Netherlands–Morocco,
empate en 90' → penales) que **Polymarket resuelve los "Will X win?" a 90 minutos incluso
en eliminatorias**, así que la doble-oportunidad aplica a **todo el torneo**, no solo a la
fase de grupos.

## Decisiones de diseño (ya tomadas)

1. **Pricing del 1X: Poisson.** El modelo ganador (Elo/Bayes/blend) elige el lado como
   hoy; el Poisson da `P(pick gana) + P(empate)` = probabilidad real del 1X. Edge = esa
   prob − precio del NO del rival; Kelly sobre ese edge.
2. **Selección: campo `bet_type` en STRATEGY.md** (`win` | `double_chance`, default `win`).
   Config-driven, sigue el patrón actual de `side_criterion`.

## Arquitectura

Encaja en las 2 capas actuales sin cambiar el flujo de decisión:

- `pick_side` **no cambia**: el modelo ganador elige el favorito (`pick`) igual que hoy.
- Cuando `strategy.bet_type == "double_chance"`, `build_worldcup_opportunity` construye la
  oportunidad contra el **mercado del rival, lado NO**, con
  `model_probability = P(pick no pierde)` del Poisson.
- El resto del pipeline (risk.evaluate → optimization.size_single → REVIEW → broker) es
  idéntico: solo cambia qué token se compra y con qué probabilidad se dimensiona.

## Componentes (unidades pequeñas y aisladas)

### 1. `core/strategy.py` — `StrategyConfig.bet_type`
- Nuevo campo `bet_type: str = "win"`.
- Validador: solo acepta `"win"` o `"double_chance"`; cualquier otro valor es error.
- Parsearlo del bloque de parámetros del STRATEGY.md (mismo mecanismo que `side_criterion`).

### 2. `venue/matching.py` — extraer el token NO
- Hoy `_extract_yes_token` devuelve solo el YES y descarta `market.outcomes.no`.
- Extender el dict devuelto con: `no_token_id: str`, `no_best_ask: Decimal | None`,
  `no_price: Decimal` (mid del NO; fallback a `1 - yes_price` si el mid del NO es None).
- Determinar el slot NO real por label (igual que hoy con el YES, por si el orden viene
  invertido).

### 3. `research/functions/market_scanner.py` — `PolymarketMarket` con lado NO
- Añadir campos opcionales: `no_token_id: str | None = None`,
  `no_best_ask: Decimal | None = None`, `no_probability: Decimal | None = None`.
- El campo `outcome: str = "YES"` ya existe y expresa qué token se compra ("YES"/"NO").
- `gateway.find_match_markets` / el builder de `PolymarketMarket` los rellena desde (2).

### 4. Helper Poisson — `research/functions/poisson_loader.py` (nuevo)
- `one_x_prob(tournament_id, home, away, pick_side) -> Decimal | None`.
- Corre `WorldCupPoissonPipeline(tournament_id).fit().forecast(home, away)` (fit cacheado
  por tournament_id por proceso, como el cache de clientes) y usa `prob_result()`:
  - `pick_side == HOME_WIN` → `home + draw`
  - `pick_side == AWAY_WIN` → `away + draw`
- Devuelve `None` si el Poisson no puede pronosticar el partido (equipo sin datos de
  goles) — no se inventa probabilidad.
- `home`/`away` se pasan con las claves que usa `load_goal_matches` (team_id del proyecto).

### 5. Resolver compartido del target de apuesta (clave para consistencia)
**Problema:** hay DOS caminos que eligen qué mercado apostar y NO comparten código:
`build_worldcup_opportunity` (pipeline de órdenes) y `scripts/scan_market.py` (que hace su
propia selección inline: `next(m for m in markets if m.model_outcome == sig.side)` + edge).
Si el `double_chance` se implementa solo en uno, el scan mostraría el ganador y las órdenes
el 1X → inconsistente y peligroso.

**Solución:** extraer una función pura compartida en `research/functions/wc_strategy.py`:

```
resolve_bet_market(pick_side, pick_model_prob, markets, strategy, one_x_prob) -> BetTarget | None
```
donde `BetTarget = {market: PolymarketMarket, model_probability: Decimal}` y `one_x_prob`
es la prob del Poisson ya calculada (inyectada, para mantener la función pura/testeable).

- `bet_type == "win"`: `market = m con model_outcome == pick_side`; `model_probability =
  pick_model_prob`. (Comportamiento actual.)
- `bet_type == "double_chance"`:
  1. `opponent = AWAY_WIN if pick == HOME_WIN else HOME_WIN`.
  2. `opp = m con model_outcome == opponent`. Si no está o sin `no_token_id` → `None`.
  3. Si `one_x is None` → `None` (se salta; no hay prob real).
  4. `market =` variante NO del `opp`: `outcome="NO"`, `token_id = opp.no_token_id`,
     `market_probability = opp.no_probability`, `best_ask = opp.no_best_ask`,
     `model_outcome = pick` (el NO resuelve a favor de "el pick no pierde").
  5. `model_probability = one_x`.
- Devuelve `None` si no hay mercado apto (ambos modos).

`build_worldcup_opportunity` usa `resolve_bet_market` y pasa su `BetTarget` a
`calculate_edge(prediction, target.market, strategy, model_probability=target.model_probability)`.

### 6. `scripts/scan_market.py` — usar el resolver + display
- Reemplazar la selección inline (`next(... model_outcome == sig.side)` + edge manual) por
  una llamada a `resolve_bet_market(...)`, calculando `one_x_prob` cuando
  `bet_type=double_chance`. Así **scan y órdenes muestran/apuestan exactamente lo mismo**.
- La columna de lado muestra el `outcome` ("YES"/"NO") + etiqueta `[1X]` cuando aplica.
- `model_prob`, `market_prob` y `edge` salen del `BetTarget` (reflejan la doble-oportunidad).

### 7. Broker / `scripts/orders.py` — colocar la orden NO
- Verificar que la colocación usa `market.token_id` + `market.outcome` genéricamente
  (compra el token indicado), de modo que comprar el NO del rival funcione sin cambios.
- Si el broker asume YES en algún punto, ajustarlo para respetar `outcome`.

## Flujo de datos (double_chance)

```
MatchPrediction (Elo/Bayes eligen favorito=pick)
  → opponent = lado contrario
  → mercado del rival, token NO  (venue.matching / find_match_markets)
  → Poisson.forecast(home, away) → P(pick)+P(draw) = one_x  (poisson_loader)
  → calculate_edge(no_market, model_probability=one_x) → edge = one_x − precio_NO
  → risk.evaluate → optimization.size_single (Kelly ¼)
  → REVIEW → broker compra el NO del rival
```

## Casos borde

- **Sin forecast Poisson** (equipo con datos de goles insuficientes) → se salta la
  oportunidad (`None`). No se apuesta sin probabilidad real.
- **Sin token NO del rival** en la lista de mercados → se salta.
- **Warmup + filtro Bayes**: se siguen aplicando sobre el pick (el gate de selección no
  cambia).
- **Todo el torneo**: sin lógica de fase; Polymarket resuelve a 90' también en knockouts.
- **Compatibilidad**: `bet_type` ausente en un STRATEGY.md viejo → default `win` →
  comportamiento idéntico al actual.

## Testing

- `core/strategy`: `bet_type` parsea de STRATEGY.md; valor inválido = error; ausente =
  `win`.
- `venue/matching`: `_extract_yes_token` (o su reemplazo) devuelve `no_token_id`,
  `no_best_ask`, `no_price`; maneja slot invertido.
- `poisson_loader.one_x_prob`: pick HOME → `home+draw`; pick AWAY → `away+draw`; sin
  forecast → `None` (con pipeline fake).
- `wc_strategy.resolve_bet_market` (con fakes, el núcleo): en `double_chance` elige el
  mercado del rival lado NO con `model_probability = one_x`; se salta (`None`) si no hay
  forecast (`one_x is None`) o no hay token NO del rival; en `win` devuelve el mercado del
  pick con `pick_model_prob` (sin cambios).
- `build_worldcup_opportunity` delega en `resolve_bet_market` y produce el edge correcto
  (1X − precio_NO) en `double_chance`.
- La economía (ROI del 1X) ya la validó el backtest — no se re-testea aquí.

## Fuera de alcance (YAGNI)

- Reglas por fase (grupos vs knockout): el 1X aplica a todo el torneo.
- Modo `both` (apostar ganador y 1X a la vez): no pedido; se puede añadir después con una
  estrategia paralela.
- Recalibrar el modelo ganador para que emita empates: el Poisson ya cubre eso.

## Restricciones globales (heredadas del proyecto)

- **Dinero real**: sin `--live` + `POLYMARKET_LIVE=1` + key + kill-switch off +
  confirmación tipeada, todo es dry-run. El nuevo modo no relaja ningún gate.
- **Una sola librería**: todo Polymarket pasa por el SDK vía el gateway; nada de scrapers.
- **Almacenamiento en UTC**; display en hora local (PDC) — no afecta este feature.
- Funciones puras testeables (2 capas: efectos vs puro); `pick_side`/`one_x_prob`/
  `build_worldcup_opportunity` son puras (reciben datos, no hacen I/O salvo el pipeline
  Poisson que lee el SQLite vía su loader ya existente).
