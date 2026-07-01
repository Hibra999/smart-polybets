# Subsistema B — Colocación/gestión de órdenes (diseño)

**Fecha:** 2026-07-01
**Estado:** aprobado (brainstorming) → pendiente plan de implementación
**Repo:** `pypro_polymarket_agent`

## Objetivo

Cerrar el loop CIO: permitir **aprobar una decisión REVIEW y colocar su orden real**
en Polymarket (con confirmación tipeada), y **cancelar órdenes abiertas**. Primer
entregable del subsistema B; el resto (order-manager de ciclo completo con fills/retry)
queda fuera.

Opera sobre **dinero real** → la seguridad manda: doble gate (env-gates del broker +
confirmación tipeada por orden), repricing live y rechazo de decisiones vencidas.

## Alcance

**Dentro de B (primer entregable):**
- `broker.cancel(order_id)` — cancelar una orden abierta vía el SDK (dry-run si no live).
- Flujo "aprobar REVIEW → colocar": validar, repreciar live, confirmar, colocar, registrar.
- CLI `scripts/orders.py`: `--list` / `--approve <key>` / `--cancel <order_id>`.

**Fuera (futuro):**
- Órdenes de mercado (`place_market_order`), seguimiento de fills parciales, retry,
  redención de posiciones, colocación ad-hoc sin decisión.

## Decisiones de diseño

- **Seguridad = doble gate.** El broker ya exige `--live` + `POLYMARKET_LIVE=1` +
  private key + kill-switch apagado para ENVIAR (si no, dry-run que imprime la orden
  simulada). B agrega **confirmación tipeada por orden** (el usuario teclea un valor
  esperado) antes de llamar al broker.
- **Repricing live obligatorio.** Nunca se coloca al precio guardado de la señal. Antes
  de colocar se obtiene el best_ask live por `token_id` y se aplica guarda de slippage
  (`validate_live_price`, tolerancia 0.15). El pricing es read-only y usa el cliente del
  SDK aunque el broker esté en dry-run.
- **Rechazo de decisiones vencidas.** Si `event_start_utc <= now` (evento empezado o
  terminado) la decisión NO es colocable. Las 3 REVIEW actuales (2026-06-20) son
  vencidas: probar en vivo requiere una REVIEW fresca de un partido por jugar.
- **Reuso.** `PolymarketBroker.place` ya está cableado y su firma coincide con
  `SecureClient.place_limit_order`. Se reusan `round_to_tick`, `validate_live_price`,
  `LocalStateClient.mark_executed`, y el `AccountSource` de A para listar órdenes vivas.

## Componentes

### `execution/functions/broker.py` (modificar)
- Añadir `PolymarketBroker.cancel(order_id: str) -> OrderResult`:
  - Dry-run (no live) → `OrderResult(status="dry_run", ...)` sin tocar la red.
  - Live → `client.cancel_order(order_id=order_id)`; mapea la respuesta a `OrderResult`
    (`status="cancelled"` si la API lo confirma, `"error"` si excepción). Nunca tira
    (captura y devuelve `OrderResult status=error`), igual que `place`.
- Añadir `PolymarketBroker.best_ask(token_id: str) -> Decimal | None`:
  - Usa el cliente del SDK (`get_order_book(token_id=...)`) para el mejor ask (precio de
    compra). Read-only; funciona aunque el broker esté en dry-run (si hay key). Devuelve
    `None` si no se puede (sin key/red/mercado). El accessor exacto del order book se
    confirma al implementar (como se hizo con la paginación de A).

### `execution/functions/review_order.py` (nuevo, puro)
- `validate_placeable(decision: dict, *, now: datetime, live_price: Decimal | None, tolerance: Decimal = Decimal("0.15")) -> tuple[bool, str]`:
  Devuelve `(ok, reason)`. Rechaza (ok=False) si: no hay `polymarket_token_id`; el evento
  ya empezó (`event_start_utc <= now`); `live_price` es None o ≤ 0; o el slippage vs la
  señal (`best_ask` guardado, o `market_probability`) supera la tolerancia
  (`validate_live_price`). `ok=True, reason="ok"` si pasa todo.
- `build_trade_order_from_decision(decision: dict, live_price: Decimal) -> TradeOrder`:
  Construye el `TradeOrder` desde `opportunity_json`: `side=OrderSide.BUY`,
  `order_type=OrderType.LIMIT`, `price=live_price`, `size_usdc=recommended_size`,
  `size_shares=size_usdc/live_price`, y `token_id`/`condition_id`/`outcome`/`neg_risk`/
  `tick_size`/`min_order_size` desde la oportunidad. (El broker reaplica `round_to_tick`
  y el mínimo en `place`.)

### `scripts/orders.py` (nuevo, CLI)
- `enable_utf8()` + `load_env()`.
- `--list` (default): tabla de REVIEWs pendientes (de `agent_state.json`, status
  `pending_approval`/verdict `REVIEW`) + órdenes abiertas live (vía `AccountSource` de A).
- `--approve <key>`: `key` es la idempotency_key (o un prefijo único). Carga la decisión →
  `broker.best_ask(token_id)` → `validate_placeable` (si falla imprime el motivo y sale) →
  `build_trade_order_from_decision` → imprime la orden EXACTA (mercado, lado, precio,
  shares, USDC, dry-run|live) → **confirmación tipeada** (input; o `--confirm <valor>` que
  debe coincidir, para uso no interactivo) → `broker.place(order)` → si el resultado no es
  error, `mark_executed(key, result)` → imprime el `OrderResult`.
- `--cancel <order_id>`: muestra la orden (de la lista de abiertas) → confirmación tipeada
  → `broker.cancel(order_id)` → imprime el resultado.
- Flags de apoyo: `--live` (pasa a `PolymarketBroker(live=True)`), `--state`, `--bankroll`,
  `--tolerance` (default 0.15), `--confirm <valor>`.

## Flujo de datos

```
scripts/orders.py --approve <key> [--live]
  → LocalStateClient carga la decisión (agent_state.json)
  → PolymarketBroker.best_ask(token_id)          (SDK order book, read-only)
  → validate_placeable(decision, now, live_price) (puro: evento/slippage/token)
  → build_trade_order_from_decision(decision, live_price)  (puro → TradeOrder)
  → imprime orden EXACTA + confirmación tipeada
  → PolymarketBroker.place(order)   (dry-run salvo --live+env+key+kill-switch off)
  → LocalStateClient.mark_executed(key, result)
```

## Manejo de errores

- Sin key / SDK / red al repreciar → `best_ask` None → `validate_placeable` rechaza
  ("no se pudo repreciar") → no coloca.
- Decisión vencida o token faltante → rechazada con motivo, exit limpio.
- Slippage > tolerancia → rechazada, sugiere re-evaluar desde research.
- El broker captura toda excepción de red/SDK y devuelve `OrderResult status=error` (nunca
  rompe el CLI).
- Confirmación tipeada que no coincide → aborta sin colocar.

## Testing

- Puro (unit, con fakes, sin red): `validate_placeable` (evento empezado, slippage alto,
  token faltante, live_price None, caso ok) y `build_trade_order_from_decision` (mapeo +
  size_shares).
- `broker.cancel` en dry-run (sin red) → `OrderResult status="dry_run"`.
- El envío/cancelación live real y `best_ask` (bordes de red/SDK) quedan sin unit-test;
  verificación manual con OK explícito del usuario, idealmente sobre una REVIEW fresca.

## Criterios de aceptación

1. `python scripts/orders.py --list` muestra REVIEWs pendientes + órdenes abiertas live
   (o mensaje accionable si la cuenta live no está disponible), sin crash en consola.
2. `--approve <key>` sobre una decisión **vencida** la rechaza con motivo claro y NO coloca.
3. En dry-run, `--approve` imprime la orden EXACTA repreciada y no envía nada.
4. `--cancel <order_id>` en dry-run muestra la orden y no envía nada.
5. La colocación/cancelación real sólo ocurre con `--live` + env-gates + confirmación
   tipeada correcta.
6. `pytest` verde, incluyendo los nuevos tests puros y el de `broker.cancel` dry-run.

## Notas

- El accessor exacto del order book del SDK (`get_order_book`) se confirma al implementar.
- Probar en vivo requiere regenerar una REVIEW fresca (correr el pipeline sobre un partido
  por jugar); las 3 actuales están vencidas.
