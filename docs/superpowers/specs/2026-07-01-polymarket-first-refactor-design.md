# Refactor Polymarket-first — diseño

**Fecha:** 2026-07-01
**Estado:** aprobado (brainstorming) → pendiente plan de implementación
**Repo:** `pypro_polymarket_agent`

## Objetivo

Reorientar el sistema a **Polymarket como mercado principal** e interactuar con él de la
manera más eficiente, con **una sola librería** (el SDK oficial `polymarket`), y dejar los
**deportes como plugins** que se pegan encima. Eliminar la complejidad accidental
(2 clientes Polymarket, 2 backends de estado, scripts solapados) **conservando** lo que se
gana su lugar (funciones puras, schemas frozen, `STRATEGY.md`, idempotencia, dry-run/gates,
139 tests). Refactor **incremental por fases**, suite verde en cada checkpoint — sin big-bang.

## Decisiones (del brainstorming)

- **Un solo plan con las 3 fases**, cada fase = checkpoint mergeable y con software funcionando.
- **Conservar las 6 áreas puras** (research/risk/optimization/execution/portfolio/editorial) y
  agregar el gateway + el seam de señales **encima** (no colapsarlas).
- **Un solo backend de estado: LocalState.** Retirar el cliente Django y sus tools.

## Arquitectura destino

### Núcleo: `polymarket/` (gateway único)
Un objeto que centraliza TODA la interacción con el venue, sobre `core.polymarket_client`:
- **Descubrimiento (PublicClient, sin auth):** `list_markets`, `list_events`, `get_event`,
  `search`, `get_sports`, `get_sports_market_types`, `get_market_tags`, `order_book`,
  `best_ask`, `price`/`price_history`, `last_trade_price`.
- **Cuenta (SecureClient, auth):** `balance`, `positions`, `open_orders`, `closed_positions`.
- **Ejecución (SecureClient, auth):** `place(TradeOrder)`, `cancel(order_id)` — con los
  mismos gates de seguridad del broker actual (dry-run por defecto).

Los tres bordes de hoy dejan de tener cliente propio y **delegan en el gateway**:
- `research/functions/polymarket_live.py` → reimplementado sobre el gateway (se retira el
  scraper `requests`/Gamma). Sigue satisfaciendo el Protocol `MarketSource`.
- `PolymarketAccountSource` → delega en `gateway.balance/positions/open_orders/closed_positions`.
- `PolymarketBroker` → delega en `gateway.place/cancel/best_ask`.

Resultado: **un cliente SDK, un lugar que habla con Polymarket**, adapters finos. Los Protocols
(`MarketSource`, `AccountSource`) se conservan como interfaz para no romper consumidores.

### Deportes como plugins: seam de señal
- `SignalProvider` (Protocol): dado un `Market` de Polymarket → `Signal | None`.
- `Signal` (schema): `model_probability`, `model_confidence`, `model_version`, `sample_size`,
  `side` (HOME_WIN/AWAY_WIN u outcome). Es el input que `research` convierte en
  `MarketOpportunity` (edge = señal − precio).
- Registro `sport → provider`. Fútbol y NFL se envuelven como providers reusando
  `research`/adapters/modelos existentes. **Pegar un deporte nuevo = registrar un provider.**

### Flujo Polymarket-first
`gateway.list_markets(sport/tag) → provider.signal(market) → MarketOpportunity → risk →
optimization → execution(gateway) → portfolio`. Las 6 áreas quedan por debajo, intactas.

## Fases (un plan; cada fase mergeable)

### Fase 1 — Gateway único + retirar Gamma
- Crear `polymarket/gateway.py` (+ `polymarket/schemas.py` si hace falta envolver tipos del SDK).
- Reapuntar `PolymarketLiveSource`, `PolymarketAccountSource`, `PolymarketBroker` al gateway.
- **Retirar** el scraper `requests` de `research/functions/polymarket_live.py` y
  `polymarket_goals.py` (descubrimiento vía `gateway`/PublicClient).
- Tests del gateway con fake del cliente SDK; smoke live read-only. Suite verde.

### Fase 2 — Un solo estado + consolidar scripts
- **Retirar** `core/django_client.py` y `agent/tools/django_sync_tools.py`; `portfolio_tools`
  usa sólo `LocalState`. Ajustar/retirar el test de integración Django.
- Consolidar los scripts de colocación solapados (`place_one`, `place_kelly`, `place_over`)
  → quedan `place_bets.py` (pipeline), `orders.py`, `account.py`, `wc_suggestions.py`.
- Suite verde.

### Fase 3 — Seam de señales (deportes como plugin)
- `SignalProvider` Protocol + `Signal` schema + registro por deporte.
- Envolver fútbol (y NFL) como providers sobre `research`/adapters.
- Entrypoint Polymarket-first (`descubrir → señal → decidir → ejecutar`) manteniendo las áreas.
- Tests del seam + un provider de ejemplo. Suite verde.

## Contratos clave

```
class PolymarketGateway:
    def __init__(self, *, live: bool = False, private_key=None, funder=None): ...
    # descubrimiento
    def list_markets(self, *, sport=None, tag=None, ...) -> list[Market]: ...
    def best_ask(self, token_id: str) -> Decimal | None: ...
    # cuenta
    def balance(self) -> AccountBalance: ...
    def positions(self) -> list[LivePosition]: ...
    def open_orders(self) -> list[OpenOrder]: ...
    def closed_positions(self, limit: int = 6) -> list[ClosedPositionLive]: ...
    # ejecución (gates: --live + POLYMARKET_LIVE=1 + key + kill-switch)
    def place(self, order: TradeOrder) -> OrderResult: ...
    def cancel(self, order_id: str) -> OrderResult: ...

class SignalProvider(Protocol):
    sport: str
    def signal(self, market: "Market") -> "Signal | None": ...
```

## No-objetivos (YAGNI)

- No colapsar las 6 áreas (decisión explícita: conservarlas).
- No order-manager de ciclo completo (fills/retry) en este refactor.
- No re-escribir los modelos deportivos (se reusan tal cual detrás de los providers).

## Seguridad (invariante en todas las fases)

Dry-run por defecto; envío real sólo con `--live` + `POLYMARKET_LIVE=1` + private key +
kill-switch apagado + confirmación tipeada (subsistema B). El gateway hereda estos gates del
broker actual. Ninguna fase relaja esto.

## Criterios de aceptación

1. **Fase 1:** una sola dependencia/cliente Polymarket; `grep` no encuentra `requests`+Gamma en
   `research/`; `account.py`/`orders.py`/sugerencias funcionan vía el gateway; suite verde.
2. **Fase 2:** no queda import de `django_client`/`django_sync_tools`; un solo backend de
   estado; scripts consolidados; suite verde.
3. **Fase 3:** existe `SignalProvider` + registro; fútbol funciona como provider; agregar un
   deporte no toca el pipeline; suite verde.
4. En todo momento: dry-run por defecto y los 139 tests (o más) en verde tras cada fase.

## Riesgos / notas

- El gateway toca red/SDK (borde): su lógica se testea con un fake del cliente; el envío/lectura
  live se verifica manualmente con OK del usuario.
- Retirar Gamma requiere confirmar que el descubrimiento por `list_events`/`search`/`tags` del
  SDK cubre el matching partido→mercado que hoy hace el scraper (validar al implementar Fase 1).
- Es un plan grande (3 fases); se ejecuta fase por fase, merge entre fases.
