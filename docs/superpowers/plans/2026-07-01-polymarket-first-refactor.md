# Refactor Polymarket-first — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.
> **Multi-fase:** este plan tiene 3 fases; **se ejecuta y mergea una fase a la vez**. Fase 1 está en detalle TDD completo. Fases 2 y 3 están a nivel de tasks (archivos/interfaces/tests/orden); sus pasos finos se expanden al iniciar cada fase, porque dependen del resultado de la anterior (la forma real del gateway y el matching validado en Fase 1). Esto es deliberado: escribir código línea-a-línea de Fases 2-3 ahora sería especulativo.

**Goal:** Unificar toda la interacción con Polymarket en un gateway único sobre el SDK oficial, retirar la complejidad accidental (2 clientes, Django, scripts solapados), y habilitar deportes como plugins de señal — conservando las áreas puras, los gates de seguridad y la suite en verde.

**Architecture:** `polymarket/gateway.py` centraliza descubrimiento (PublicClient), cuenta y ejecución (SecureClient vía `core.polymarket_client`). Los adapters existentes (`PolymarketLiveSource`, `PolymarketAccountSource`, `PolymarketBroker`) pasan a delegar en el gateway. Un `SignalProvider` por deporte produce la probabilidad para un mercado. Refactor incremental, suite verde por fase.

**Tech Stack:** Python 3.11+, Pydantic v2 frozen, pytest, SDK `polymarket` 0.1.0b11 (import `polymarket`).

## Global Constraints

- Funciones puras en `functions/`; el borde SDK/red vive en el gateway.
- Un solo cliente Polymarket: el SDK oficial vía `core.polymarket_client.build_secure_client` (auth) y `PublicClient` (descubrimiento). Prohibido `requests` a Gamma.
- Dry-run por defecto; envío real sólo con `--live` + `POLYMARKET_LIVE=1` + key + kill-switch off + confirmación tipeada. Ninguna fase lo relaja.
- Dinero en `Decimal` (`core.utils.to_decimal`), nunca `float` salvo en el borde del SDK.
- Schemas Pydantic **frozen**; contratos inmutables (v2, no in-place).
- Scripts llaman `enable_utf8()` + `load_env()`.
- Tests con `python -m pytest`; correr con `--deselect` NO es necesario (el test time-dependent ya se arregló). Suite base: 139 verde.
- Cada fase: rama propia desde `main`, merge al terminar, suite verde antes de mergear.

---

# FASE 1 — Gateway único + retirar Gamma

Rama sugerida: `feat/polymarket-gateway`.

### Task 1.1: `PolymarketGateway` — cuenta + órdenes + best_ask (reusa A/B)

**Files:**
- Create: `polymarket/__init__.py`, `polymarket/gateway.py`
- Test: `tests/unit/test_gateway_account.py`

**Interfaces:**
- Consumes: `core.polymarket_client.build_secure_client`; schemas `AccountBalance`, `LivePosition`, `OpenOrder`, `ClosedPositionLive` (`portfolio.schemas.account`); `TradeOrder`, `OrderResult` (`execution.schemas`); `core.utils.to_decimal/utcnow`.
- Produces: `PolymarketGateway(*, live=False, private_key=None, funder=None)` con métodos `balance()`, `positions()`, `open_orders()`, `closed_positions(limit=6)`, `best_ask(token_id)`, `place(order)`, `cancel(order_id)`.

Nota: el cuerpo de estos métodos ES el que hoy vive en `PolymarketAccountSource` (mapeo de `list_positions`/`list_closed_positions`/`get_balance_allowance`/`list_open_orders`) y en `PolymarketBroker` (`place`/`cancel`/`best_ask` con los gates). Este task los **centraliza** en el gateway; los adapters se reapuntan en 1.3.

- [ ] **Step 1: Test (fake client) — balance + place dry-run + best_ask**

```python
# tests/unit/test_gateway_account.py
from decimal import Decimal
from polymarket.gateway import PolymarketGateway

class _Book:  # asks: lista de niveles con .price
    def __init__(self, asks): self.asks = asks
class _Lvl:
    def __init__(self, p): self.price = Decimal(str(p))
class _BA:
    balance = 448620000   # micro-USDC

class _FakeClient:
    def get_balance_allowance(self, *, asset_type, token_id=None): return _BA()
    def get_order_book(self, *, token_id): return _Book([_Lvl("0.47"), _Lvl("0.52")])

def _gw():
    gw = PolymarketGateway(live=False)
    gw._client = _FakeClient()          # inyecta el fake (evita red)
    gw.private_key = "0xabc"            # para que best_ask no corte por falta de key
    return gw

def test_balance_micro_to_usdc():
    assert _gw().balance().usdc_balance == Decimal("448.62")

def test_best_ask_min_of_asks():
    assert _gw().best_ask("t") == Decimal("0.47")
```

- [ ] **Step 2: Run → FAIL** (`ModuleNotFoundError: polymarket.gateway`).
  Run: `python -m pytest tests/unit/test_gateway_account.py -q`

- [ ] **Step 3: Implement** `polymarket/gateway.py`. Portar TAL CUAL la lógica de
  `portfolio/functions/account_source.py` (balance/positions/open_orders/closed_positions,
  `_ensure_client` vía `build_secure_client`, `best_ask` del order book: `min(l.price for l in book.asks)`)
  y de `execution/functions/broker.py` (`place`/`cancel` con `_prepare`, gates `live`,
  round_to_tick, min size). El gateway expone `_client`, `private_key`, `funder`, `live`.
  (Añadir `polymarket/__init__.py` vacío y `polymarket` a `packages` en `pyproject.toml`.)

- [ ] **Step 4: Run → PASS** (2 passed).
- [ ] **Step 5: Commit** — `feat(polymarket): PolymarketGateway (cuenta+órdenes+best_ask centralizados)`

### Task 1.2: Gateway — descubrimiento de mercados vía SDK (reemplazo de Gamma)

**Files:**
- Modify: `polymarket/gateway.py`
- Create: `polymarket/matching.py` (canon/alias de nombres, portado de `polymarket_live.py`)
- Test: `tests/unit/test_gateway_matching.py`

**Interfaces:**
- Produces: `PolymarketGateway.find_match_markets(home:str, away:str) -> list[PolymarketMarket]`
  (mismo `PolymarketMarket` de `research.functions.market_scanner`), y helpers puros en
  `matching.py`: `canon(name)->str`, `match_event(event, home, away)->dict|None`.

- [ ] **Step 1: Test** — `matching.canon` normaliza acentos/alias (p. ej. `"Côte d'Ivoire"→"ivorycoast"`, `"Türkiye"→"turkiye"`); `match_event` empareja un Event fake (`title="Netherlands vs. Sweden"`, `markets=[Will Netherlands win…]`) al par (home,away) y devuelve el token del outcome. (Reusar las tablas `_ALIASES` y la regex `Will X win` de `research/functions/polymarket_live.py`.)
- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement.** Portar `canon`/`_ALIASES`/regex desde `polymarket_live.py` a `matching.py` (funciones puras, testeables sin red). En el gateway, `find_match_markets` usa `PublicClient.list_events(tag=..., closed=False)` (o `search`), y para cada `Event` aplica `match_event` sobre `event.markets` (campos `condition_id`, `question`, `outcomes`, `prices`, y los ids de token del SDK) → construye `PolymarketMarket` con `model_outcome` HOME_WIN/AWAY_WIN. **Validar contra el SDK live** el nombre exacto de los campos de token/precio del `Market` (introspección + un run real) antes de cerrar el task.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `feat(polymarket): descubrimiento+matching de mercados vía SDK (sin Gamma)`

### Task 1.3: Reapuntar adapters al gateway + retirar el scraper Gamma

**Files:**
- Modify: `research/functions/polymarket_live.py` (reimplementar `PolymarketLiveSource` sobre el gateway), `portfolio/functions/account_source.py` (delegar en gateway), `execution/functions/broker.py` (delegar en gateway)
- Remove: el uso de `requests`/`gamma-api` en `polymarket_live.py` y `research/functions/polymarket_goals.py`
- Test: los existentes `test_account_source.py`, `test_broker*.py`, `test_research_and_sizing.py` deben seguir verdes

**Interfaces:**
- `PolymarketLiveSource.__call__(prediction)` sigue devolviendo `list[PolymarketMarket]` (Protocol `MarketSource` intacto), ahora vía `gateway.find_match_markets(prediction.participant_home, prediction.participant_away)`.
- `PolymarketAccountSource.*` y `PolymarketBroker.*` delegan en una instancia de `PolymarketGateway` (los tests de A/B siguen pasando: mismos tipos de retorno y mismos gates).

- [ ] **Step 1:** Reapuntar cada adapter a un `PolymarketGateway` interno; borrar imports/uso de `requests` y la URL de Gamma. `polymarket_goals.py`: migrar a `gateway.find_match_markets`/`list_markets` o retirar si no se usa (verificar consumidores).
- [ ] **Step 2:** Run suite completa. `grep -rn "requests\|gamma-api" research/` → vacío.
- [ ] **Step 3:** Smoke live read-only: `python scripts/account.py` y `python scripts/orders.py --list` funcionan vía gateway.
- [ ] **Step 4: Commit** — `refactor(polymarket): adapters delegan en el gateway; retira scraper Gamma`

### Task 1.4: Fase 1 verde + merge

- [ ] Suite completa verde (`python -m pytest`). Un solo cliente Polymarket; `grep` sin `requests`+Gamma en `research/`.
- [ ] Merge `feat/polymarket-gateway` → `main` (`--no-ff`), suite verde en main.

---

# FASE 2 — Un solo estado + consolidar scripts

Rama sugerida: `feat/state-and-scripts-cleanup`. (Tasks a expandir a TDD fino al iniciar la fase.)

### Task 2.1: Retirar el backend Django
- **Files:** Remove `core/django_client.py`, `agent/tools/django_sync_tools.py`, `tests/integration/django_sync/test_django_client.py`; Modify `agent/tools/portfolio_tools.py` (que hoy inyecta un `DjangoClient`) para usar sólo `LocalStateClient`; Modify `agent/workflows/full_analysis.py` y cualquier consumidor del tipo `DjangoClient`.
- **Deliverable/test:** `grep -rn "django" --include=*.py` sin resultados de código; `portfolio_tools` opera contra `LocalState`; `test_full_analysis.py` ajustado (inyecta `LocalStateClient`); suite verde.
- **Interfaz:** `portfolio_tools.get_state/check_idempotency/save_decision/mark_executed(client=LocalStateClient)`.

### Task 2.2: Consolidar scripts de colocación
- **Files:** Remove/retire `scripts/place_one.py`, `scripts/place_kelly.py`, `scripts/place_over.py` (flujos ad-hoc solapados); conservar `scripts/place_bets.py` (pipeline AUTO), `scripts/orders.py` (aprobar/cancelar), `scripts/account.py`, `scripts/wc_suggestions.py`. Si `place_kelly/over` tienen lógica útil no cubierta (p. ej. mercados O/U de goles), migrarla a `orders.py`/`research` antes de borrar.
- **Deliverable/test:** `ls scripts/` sin los `place_*` redundantes; `EXECUTION_GOLIVE.md` actualizado; suite verde; smoke de los scripts conservados.

### Task 2.3: Fase 2 verde + merge
- Suite verde; un solo backend de estado; scripts consolidados; merge a `main`.

---

# FASE 3 — Seam de señales (deportes como plugin)

Rama sugerida: `feat/signal-seam`. (Tasks a expandir a TDD fino al iniciar la fase; dependen del `Market`/gateway de Fase 1.)

### Task 3.1: `SignalProvider` + `Signal` + registro
- **Files:** Create `signals/__init__.py`, `signals/base.py` (`Signal` schema + `SignalProvider` Protocol), `signals/registry.py` (`register(sport, provider)` / `get(sport)`).
- **Interfaz:** `class Signal(BaseModel, frozen): model_probability:Decimal; side:str; model_confidence:str; model_version:str; sample_size:int` · `class SignalProvider(Protocol): sport:str; def signal(self, market)->Signal|None`.
- **Deliverable/test:** registro devuelve el provider por deporte; un provider fake produce un `Signal`; test puro.

### Task 3.2: Provider de fútbol sobre `research`/adapters
- **Files:** Create `signals/football.py` (envuelve `research.get_event_prediction` + `wc_strategy.pick_side` para, dado un `Market`, resolver el fixture y devolver `Signal`).
- **Deliverable/test:** con un adapter/reader fake, el provider produce la misma prob que el pipeline actual para un fixture conocido; test.

### Task 3.3: Entrypoint Polymarket-first
- **Files:** Create `scripts/scan_market.py` (o extender `wc_suggestions`): `gateway.list_markets(sport) → provider.signal → calculate_edge → risk → sizing` mostrando oportunidades por mercado. Las 6 áreas quedan por debajo, sin cambios.
- **Deliverable/test:** un run dry-run lista oportunidades desde mercados de Polymarket; agregar un deporte = registrar un provider (documentar en `signals/README.md`); suite verde.

### Task 3.4: Fase 3 verde + merge
- Suite verde; `SignalProvider` + registro + provider de fútbol; merge a `main`.

---

## Self-review (contra el spec)
- Cobertura: 1 librería (F1.1–1.3) ✓ · retirar Gamma (F1.3) ✓ · 1 estado/retirar Django (F2.1) ✓ · consolidar scripts (F2.2) ✓ · seam de señales (F3.1–3.3) ✓ · conservar áreas ✓ · gates de seguridad invariantes ✓.
- Fase 1 en detalle TDD; Fases 2-3 a nivel de tasks con archivos/interfaces/tests, a expandir al iniciar cada fase (dependencia entre fases). Sin placeholders dentro de los steps de Fase 1.
- Consistencia de tipos: `PolymarketGateway` (métodos 1.1) reusados por adapters (1.3); `Signal`/`SignalProvider` (3.1) consumidos por football provider (3.2) y entrypoint (3.3).
