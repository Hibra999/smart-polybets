# Subsistema A — Cuenta / lecturas live (diseño)

**Fecha:** 2026-07-01
**Estado:** aprobado (brainstorming) → pendiente plan de implementación
**Repo:** `pypro_polymarket_agent`

## Objetivo

Dar al agente visibilidad **live** de la cuenta de Polymarket: **saldo pUSD**,
**posiciones abiertas** (con mark-to-market) y **órdenes abiertas** del CLOB V2, más
un comando de **reconciliación** explícito contra el ledger local (`agent_state.json`).
Es el primer subsistema de tres (A: lecturas live · B: colocación/gestión de órdenes ·
C: armado de estrategias); B y C se apoyan en A.

Todo se entrega como **tools deterministas** reutilizables (en `agent/tools/` +
`scripts/`), para invocarlas sin reconstruir lógica cada vez.

## Alcance

**Dentro de A:**
- Lectura live de saldo pUSD, posiciones y órdenes abiertas (autenticado vía SDK V2).
- Mark-to-market de posiciones abiertas (PnL no realizado con precio live de Gamma).
- Vista de consola: snapshot completo de la wallet, con **filtro opcional por evento**
  (y por torneo). Muestra **todas** las posiciones/órdenes; etiqueta cada una con
  torneo/estrategia si su `condition_id` mapea a una decisión local, o "externa" si no.
- Comando `--reconcile` explícito: reporte de drift + ajuste de bankroll al balance real.

**Fuera de A (subsistemas B/C):**
- Colocar/cancelar/reintentar órdenes; wiring de `execution.submit_order` (subsistema B).
- Definir/backtestear estrategias (subsistema C).

## Decisiones de diseño

- **Auth:** todo autenticado vía el SDK oficial V2 `polymarket-client` (private key).
  No hay ruta read-only por address público. Las **lecturas NO requieren
  `POLYMARKET_LIVE=1`** (ese flag solo habilita el *envío* de órdenes); basta la key.
- **Ubicación:** área `portfolio/` (ya es el puente de estado/PnL), sin crear área nueva.
- **Patrón:** fuente inyectable con stub por defecto, igual que `PolymarketLiveSource`
  (Gamma) y `PolymarketBroker`. La lógica es pura y testeable; el adapter SDK es el
  borde delgado.
- **Reconciliación:** solo bajo `--reconcile` (escritura explícita). El modo default
  nunca escribe estado.
- **Realidad del entorno:** el SDK V2 (`polymarket-client>=0.1.0b8`, beta pre-release)
  **no está instalado** en el intérprete activo y `.env` no tiene private key. Por eso el
  adapter live queda detrás del Protocol con los call sites marcados `TODO(wiring-sdk)`;
  la lógica se prueba con fakes ahora y el adapter se verifica live en la wallet del
  usuario tras `pip install --pre .[live]` + configurar la key.

## Componentes

### `portfolio/schemas/account.py` (nuevo)
Schemas Pydantic frozen:
- `AccountBalance`: `usdc_balance: Decimal` (pUSD disponible), `as_of: datetime`,
  `address: str | None`.
- `LivePosition`: `condition_id`, `token_id`, `outcome`, `size_shares: Decimal`,
  `avg_entry_price: Decimal`, `current_price: Decimal | None`, `event_id: str | None`,
  `tournament_id: str | None`, `strategy_id: str | None`. `unrealized_pnl` es una
  **propiedad computada** = `(current_price - avg_entry_price) * size_shares` cuando
  hay `current_price`, si no `None` (igual patrón que `portfolio.schemas.Position`).
- `OpenOrder`: `order_id`, `condition_id`, `token_id`, `side` (BUY/SELL), `price:
  Decimal`, `size_shares: Decimal`, `size_matched: Decimal`, `status`, `created_at`,
  `event_id: str | None`.

### `portfolio/functions/account_source.py` (nuevo)
- `AccountSource` (Protocol): `get_balance() -> AccountBalance`,
  `get_positions() -> list[LivePosition]`, `get_open_orders() -> list[OpenOrder]`.
- `PolymarketAccountSource`: adapter live (SDK V2 + key). Constructor recibe la config
  (key/funder desde env). Cada método envuelve la llamada del SDK (marcada
  `TODO(wiring-sdk)`) y normaliza la respuesta a los schemas. Si el SDK no está
  importable o falta la key, lanza `AccountUnavailableError` con mensaje accionable.
- La inyección permite un fake en tests (no se provee un stub "vacío" productivo: sin
  cuenta live, el CLI reporta indisponibilidad en vez de inventar datos).

### `portfolio/functions/account_reconcile.py` (nuevo, puro)
- `mark_to_market(positions, price_of) -> list[LivePosition]`: devuelve copias con
  `current_price` poblado (best_bid live, valor de salida); `unrealized_pnl` deriva como
  propiedad. `price_of` es un callable inyectable (adaptador sobre
  `PolymarketLiveSource`) → testeable sin red.
- `tag_positions(positions, decisions) -> list[LivePosition]`: mapea `condition_id` →
  decisión local para poblar `event_id`/`tournament_id`/`strategy_id`; deja `None` si no
  mapea (posición "externa").
- `reconcile(decisions, balance, positions, *, bankroll_param) -> ReconcileReport`:
  compara realidad vs ledger. `ReconcileReport` (dict o schema liviano) con:
  - `bankroll_param` vs `balance.usdc_balance` (delta).
  - decisiones locales `executed` sin posición on-chain correspondiente (¿no se llenó?).
  - posiciones on-chain sin decisión local ("externas").
  - resumen para impresión.
  La función es pura (no escribe); la escritura (ajuste de bankroll, registro de drift)
  la hace el script bajo `--reconcile`.

### `agent/tools/account_tools.py` (nuevo)
Tools deterministas que inyectan la `AccountSource` y devuelven los schemas:
`get_balance()`, `get_positions()` (con mark-to-market + tagging), `get_open_orders()`,
`account_snapshot()` (los tres juntos + totales). Estas son las funciones que el agente
invoca sin reconstruir lógica.

### `scripts/account.py` (nuevo, CLI)
- Llama `enable_utf8()` (consola Windows).
- Flags: `--state data/agent_state.json`, `--bankroll`, `--event <event_id>`
  (filtro), `--tournament <id>` (filtro), `--reconcile`, `--json`.
- Default: snapshot read-only → tablas de SALDO, POSICIONES (con mark-to-market y
  etiqueta torneo/evento/estrategia o "externa") y ÓRDENES ABIERTAS. `--event`/
  `--tournament` filtran por el tag mapeado.
- `--reconcile`: imprime el `ReconcileReport` y ajusta el bankroll local al balance
  real (única escritura, explícita).
- Si la cuenta live no está disponible (sin SDK/key): mensaje accionable y exit
  limpio (no traceback).

### `tests/unit/test_account_reconcile.py` (nuevo)
Con `AccountSource` fake + `price_of` fake:
- `mark_to_market`: PnL no realizado correcto (ganadora/perdedora/sin precio).
- `tag_positions`: mapea por `condition_id`; deja "externa" cuando no mapea.
- `reconcile`: detecta delta de bankroll, decisiones sin fill, y posiciones externas.
- Sin dependencia del SDK ni de red.

## Flujo de datos

```
scripts/account.py
  → account_tools.account_snapshot(source, price_source, decisions)
       AccountSource(SDK V2)  → balance / positions / open_orders
       mark_to_market(positions, price_of=Gamma best_bid)
       tag_positions(positions, decisions del estado local)
  → (default) imprime tablas (filtradas por --event/--tournament)
  → (--reconcile) reconcile(...) → report + ajuste de bankroll
```

## Manejo de errores

- SDK no importable / sin key → `AccountUnavailableError`; el CLI lo captura e imprime
  "cuenta live no disponible (instala `.[live]` + `POLYMARKET_PRIVATE_KEY`)".
- Errores de red del SDK/Gamma → se propagan como mensaje, no rompen con traceback en
  el CLI; el snapshot indica qué sección falló.
- Las lecturas nunca dependen de `POLYMARKET_LIVE` ni del kill-switch (son read-only).

## Testing

- Unit: lógica pura (`mark_to_market`, `tag_positions`, `reconcile`) con fakes → parte
  de la suite (`pytest`), sin SDK/key/red.
- El adapter `PolymarketAccountSource` queda como borde delgado sin cobertura unit
  (llamadas al SDK); su verificación es live, manual, en la wallet del usuario.

## Criterios de aceptación

1. `python scripts/account.py` imprime saldo, posiciones (con PnL no realizado) y
   órdenes abiertas — o un mensaje accionable si no hay cuenta live — sin crash en
   consola cp1252.
2. `--event`/`--tournament` filtran correctamente; sin filtro se muestran todas.
3. `--reconcile` produce el reporte de drift y ajusta el bankroll local (solo con el flag).
4. La suite `pytest` pasa, incluyendo los nuevos tests de reconcile con fakes.
5. Los call sites del SDK están aislados tras `AccountSource` y marcados
   `TODO(wiring-sdk)` para activarse con `.[live]` + key sin tocar la lógica.

## Notas / pendientes

- El repo no está bajo git → el spec no se commitea (recomendado `git init`).
- Los nombres exactos de métodos del SDK V2 se confirmarán al instalar `.[live]`; el
  Protocol aísla ese riesgo.
