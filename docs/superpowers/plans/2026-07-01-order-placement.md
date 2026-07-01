# Colocación/gestión de órdenes (subsistema B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar el loop CIO — aprobar una decisión REVIEW y colocar su orden real (con repricing live + confirmación tipeada), y cancelar órdenes abiertas.

**Architecture:** `PolymarketBroker` gana `cancel()` y `best_ask()` (bordes SDK). Funciones puras en `execution/functions/review_order.py` validan y construyen el `TradeOrder` desde la decisión guardada. El CLI `scripts/orders.py` orquesta list/approve/cancel con doble gate (env-gates del broker + confirmación tipeada).

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, SDK `polymarket` (import) 0.1.0b11. Git ya inicializado (rama sugerida `feat/order-placement` desde `main`).

## Global Constraints

- Funciones puras en `functions/` (sin red/estado). El borde SDK vive en el broker o el script.
- Dinero real: colocar/cancelar en vivo sólo con `--live` + `POLYMARKET_LIVE=1` + private key + kill-switch apagado **Y** confirmación tipeada correcta. Sin eso → dry-run (imprime, no envía).
- Nunca colocar al precio guardado: repreciar best_ask live y aplicar guarda de slippage (tolerancia default `Decimal("0.15")`).
- Rechazar decisiones cuyo `event_start_utc <= now`.
- Dinero en `Decimal` (`core.utils.to_decimal`), nunca `float` salvo en el borde del SDK.
- El broker NUNCA lanza dentro del pipeline: captura y devuelve `OrderResult status="error"`.
- Scripts llaman `core.console.enable_utf8()` y `core.env.load_env()` tras el `sys.path.insert`.
- Tests con `python -m pytest` desde la raíz.
- Enums: `core.types.OrderSide.BUY` (`"BUY"`), `core.types.OrderType.LIMIT` (`"LIMIT"`).

---

### Task 1: `PolymarketBroker.cancel` + `best_ask`

**Files:**
- Modify: `execution/functions/broker.py`
- Test: `tests/unit/test_broker_cancel.py`

**Interfaces:**
- Consumes: `OrderResult` (`execution.schemas.order_result`), el `_get_client()` existente.
- Produces:
  `PolymarketBroker.cancel(self, order_id: str) -> OrderResult` (dry-run → `status="dry_run"`; live → `cancel_order`, `status="cancelled"`/`"error"`);
  `PolymarketBroker.best_ask(self, token_id: str) -> Decimal | None` (mejor ask del order book vía SDK; `None` si no se puede).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_broker_cancel.py
from decimal import Decimal

from execution.functions.broker import PolymarketBroker


def test_cancel_dry_run_when_not_live(monkeypatch):
    monkeypatch.delenv("POLYMARKET_LIVE", raising=False)
    broker = PolymarketBroker(live=False)
    res = broker.cancel("ord-123")
    assert res.status == "dry_run"
    assert res.order_id == "ord-123"
    assert res.filled_size_usdc == Decimal("0")
    assert res.raw.get("action") == "cancel"


def test_best_ask_returns_none_without_client(monkeypatch):
    # Sin key ni SDK utilizable, best_ask degrada a None (no rompe).
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
    broker = PolymarketBroker(live=False, private_key="")
    assert broker.best_ask("0xtoken") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_broker_cancel.py -v`
Expected: FAIL con `AttributeError: 'PolymarketBroker' object has no attribute 'cancel'`.

- [ ] **Step 3: Write minimal implementation**

En `execution/functions/broker.py`, añadir estos dos métodos dentro de la clase
`PolymarketBroker` (después de `place`). Nota: `best_ask` construye el cliente aunque
el broker esté en dry-run (pricing es read-only); captura cualquier fallo → `None`.

```python
    def best_ask(self, token_id: str) -> Decimal | None:
        """Mejor ask (precio de compra) del order book live. None si no se puede."""
        if not self.private_key:
            return None
        try:
            book = self._get_client().get_order_book(token_id=token_id)
        except Exception:  # noqa: BLE001 — pricing best-effort, nunca rompe
            return None
        asks = getattr(book, "asks", None) or []
        prices = [to_decimal(level.price) for level in asks]
        return min(prices) if prices else None

    def cancel(self, order_id: str) -> OrderResult:
        """Cancela una orden abierta (dry-run salvo live)."""
        base = {"action": "cancel", "order_id": order_id}
        if not self.live:
            return OrderResult(
                order_id=order_id, status="dry_run", filled_size_usdc=Decimal("0"),
                avg_price=None, submitted_at=utcnow(),
                raw={**base, "dry_run": True, "blocked_reason": self._blocked_reason},
            )
        try:
            resp = self._get_client().cancel_order(order_id=order_id)
            return OrderResult(
                order_id=order_id, status="cancelled", filled_size_usdc=Decimal("0"),
                avg_price=None, submitted_at=utcnow(),
                raw={**base, "response": str(resp)[:500]},
            )
        except Exception as exc:  # noqa: BLE001
            return OrderResult(
                order_id=order_id, status="error", filled_size_usdc=Decimal("0"),
                avg_price=None, submitted_at=utcnow(),
                raw={**base, "error": f"{type(exc).__name__}: {exc}"},
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_broker_cancel.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add execution/functions/broker.py tests/unit/test_broker_cancel.py
git commit -m "feat(broker): cancel() + best_ask() sobre el SDK V2 (dry-run seguro)"
```

---

### Task 2: `review_order.py` — validación + construcción del TradeOrder (puro)

**Files:**
- Create: `execution/functions/review_order.py`
- Test: `tests/unit/test_review_order.py`

**Interfaces:**
- Consumes: `TradeOrder` (`execution.schemas.trade_order`), `OrderSide`/`OrderType`
  (`core.types`), `validate_live_price` (`execution.functions.price_validator`),
  `to_decimal` (`core.utils`).
- Produces:
  `validate_placeable(decision: dict, *, now: datetime, live_price: Decimal | None, tolerance: Decimal = Decimal("0.15")) -> tuple[bool, str]`;
  `build_trade_order_from_decision(decision: dict, live_price: Decimal) -> TradeOrder`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_review_order.py
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from core.types import OrderSide, OrderType
from execution.functions.review_order import (
    build_trade_order_from_decision,
    validate_placeable,
)

NOW = datetime(2026, 6, 20, 10, 0, tzinfo=timezone.utc)


def _decision(**over):
    opp = {
        "polymarket_token_id": "81043", "polymarket_condition_id": "0xcond",
        "outcome": "YES", "best_ask": "0.58", "market_probability": "0.575",
        "neg_risk": True, "tick_size": "0.01", "min_order_size": "5",
        "event_start_utc": "2026-06-20T13:00:00Z",
    }
    opp.update(over.pop("opp", {}))
    d = {"idempotency_key": "k1", "recommended_size": "50.00", "status": "pending_approval",
         "verdict": "REVIEW", "condition_id": "0xcond", "opportunity_json": opp}
    d.update(over)
    return d


def test_placeable_ok_when_fresh_and_price_close():
    ok, reason = validate_placeable(_decision(), now=NOW, live_price=Decimal("0.60"))
    assert ok is True and reason == "ok"


def test_rejects_started_event():
    late = datetime(2026, 6, 20, 14, 0, tzinfo=timezone.utc)  # después del kickoff 13:00
    ok, reason = validate_placeable(_decision(), now=late, live_price=Decimal("0.58"))
    assert ok is False and "empez" in reason.lower()


def test_rejects_missing_token():
    ok, reason = validate_placeable(_decision(opp={"polymarket_token_id": ""}),
                                    now=NOW, live_price=Decimal("0.58"))
    assert ok is False and "token" in reason.lower()


def test_rejects_no_live_price():
    ok, reason = validate_placeable(_decision(), now=NOW, live_price=None)
    assert ok is False and "repreci" in reason.lower()


def test_rejects_high_slippage():
    # señal 0.58, live 0.80 → +38% > 15%
    ok, reason = validate_placeable(_decision(), now=NOW, live_price=Decimal("0.80"))
    assert ok is False and "slippage" in reason.lower()


def test_build_trade_order_maps_fields_and_shares():
    order = build_trade_order_from_decision(_decision(), Decimal("0.50"))
    assert order.token_id == "81043"
    assert order.condition_id == "0xcond"
    assert order.side == OrderSide.BUY
    assert order.order_type == OrderType.LIMIT
    assert order.price == Decimal("0.50")
    assert order.size_usdc == Decimal("50.00")
    assert order.size_shares == Decimal("100")          # 50 / 0.50
    assert order.neg_risk is True
    assert order.tick_size == Decimal("0.01")
    assert order.min_order_size == Decimal("5")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_review_order.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'execution.functions.review_order'`.

- [ ] **Step 3: Write minimal implementation**

```python
# execution/functions/review_order.py
"""Aprobación de una decisión REVIEW → TradeOrder. Funciones puras (sin red).

`validate_placeable` decide si una decisión guardada se puede colocar AHORA
(evento no empezado, token válido, precio live sano, slippage dentro de tolerancia).
`build_trade_order_from_decision` arma el TradeOrder al precio live (nunca al de la
señal guardada).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from core.types import OrderSide, OrderType
from core.utils import to_decimal
from execution.functions.price_validator import validate_live_price
from execution.schemas.trade_order import TradeOrder


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def validate_placeable(
    decision: dict,
    *,
    now: datetime,
    live_price: Decimal | None,
    tolerance: Decimal = Decimal("0.15"),
) -> tuple[bool, str]:
    opp = decision.get("opportunity_json") or {}
    token = opp.get("polymarket_token_id")
    if not token:
        return False, "sin token_id en la decisión"
    start = opp.get("event_start_utc")
    if start and _parse_utc(start) <= now:
        return False, "el evento ya empezó/terminó"
    if live_price is None or to_decimal(live_price) <= 0:
        return False, "no se pudo repreciar (best_ask live no disponible)"
    signal = opp.get("best_ask") or opp.get("market_probability")
    if signal is None:
        return False, "sin precio de señal para comparar slippage"
    if not validate_live_price(signal, live_price, tolerance):
        return False, f"slippage: live {live_price} vs señal {signal} > {tolerance}"
    return True, "ok"


def build_trade_order_from_decision(decision: dict, live_price: Decimal) -> TradeOrder:
    opp = decision.get("opportunity_json") or {}
    price = to_decimal(live_price)
    size_usdc = to_decimal(decision.get("recommended_size", 0))
    shares = (size_usdc / price) if price > 0 else Decimal("0")
    tick = opp.get("tick_size")
    minsz = opp.get("min_order_size")
    return TradeOrder(
        condition_id=opp.get("polymarket_condition_id") or decision.get("condition_id", ""),
        token_id=str(opp.get("polymarket_token_id", "")),
        outcome=opp.get("outcome", "YES"),
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=price,
        size_usdc=size_usdc,
        size_shares=shares,
        neg_risk=bool(opp.get("neg_risk", False)),
        tick_size=to_decimal(tick) if tick is not None else None,
        min_order_size=to_decimal(minsz) if minsz is not None else None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_review_order.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add execution/functions/review_order.py tests/unit/test_review_order.py
git commit -m "feat(execution): review_order — validate_placeable + build_trade_order (puros)"
```

---

### Task 3: CLI `scripts/orders.py` (list / approve / cancel)

**Files:**
- Create: `scripts/orders.py`
- Modify: `EXECUTION_GOLIVE.md` (documentar el comando)

**Interfaces:**
- Consumes: `PolymarketBroker` (+ `cancel`/`best_ask`, Task 1), `validate_placeable` +
  `build_trade_order_from_decision` (Task 2), `LocalStateClient` (+ `mark_executed`),
  `PolymarketAccountSource` + `account_tools.get_open_orders` (subsistema A),
  `enable_utf8`, `load_env`, `utcnow`.

- [ ] **Step 1: Escribir el CLI**

```python
# scripts/orders.py
#!/usr/bin/env python
"""Aprobar decisiones REVIEW → colocar la orden real, y cancelar órdenes abiertas.

    python scripts/orders.py --list                       # REVIEWs pendientes + órdenes abiertas
    python scripts/orders.py --approve <key> [--live]      # coloca la orden de esa decisión
    python scripts/orders.py --cancel <order_id> [--live]  # cancela una orden abierta

DINERO REAL: sin --live (+ POLYMARKET_LIVE=1 + key + kill-switch off) todo es dry-run.
Además, cada colocación/cancelación pide CONFIRMACIÓN TIPEADA (o --confirm <valor>).
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8
from core.env import load_env

enable_utf8()
load_env(Path(__file__).resolve().parent.parent / ".env")

from agent.tools import account_tools
from core.exceptions import AccountUnavailableError
from core.local_state import LocalStateClient
from core.utils import to_decimal, utcnow
from execution.functions.broker import PolymarketBroker
from execution.functions.review_order import (
    build_trade_order_from_decision,
    validate_placeable,
)
from portfolio.functions.account_source import PolymarketAccountSource


def _pending_reviews(decisions: dict) -> list[tuple[str, dict]]:
    out = []
    for key, d in decisions.items():
        if d.get("status") == "pending_approval" or d.get("verdict") == "REVIEW":
            out.append((key, d))
    return out


def _confirm(expected: str, provided: str | None) -> bool:
    if provided is not None:
        return provided.strip() == expected
    try:
        typed = input(f"    Para confirmar, escribí exactamente '{expected}': ")
    except EOFError:
        return False
    return typed.strip() == expected


def cmd_list(decisions: dict) -> None:
    reviews = _pending_reviews(decisions)
    print(f"\n=== REVIEWs pendientes ({len(reviews)}) ===")
    for key, d in reviews:
        opp = d.get("opportunity_json") or {}
        print(f"  {key[:10]}  {opp.get('participant_home','?')} vs {opp.get('participant_away','?')}"
              f"  reco={d.get('recommended_size')}  edge={d.get('edge')}  ki={opp.get('event_start_utc')}")
    print("\n=== Órdenes abiertas (live) ===")
    try:
        orders = account_tools.get_open_orders(PolymarketAccountSource())
    except AccountUnavailableError as exc:
        print(f"  (cuenta live no disponible: {exc})")
        return
    if not orders:
        print("  (ninguna)")
    for o in orders:
        print(f"  {o.order_id[:14]}  {o.side}  price={o.price}  size={o.size_shares}"
              f"  matched={o.size_matched}  {o.condition_id[:12]}…")


def cmd_approve(key: str, *, decisions: dict, client: LocalStateClient,
                broker: PolymarketBroker, tolerance: Decimal, confirm: str | None) -> None:
    match = [(k, d) for k, d in decisions.items() if k == key or k.startswith(key)]
    if len(match) != 1:
        print(f"  clave ambigua o no encontrada: {key} ({len(match)} coincidencias)")
        return
    full_key, decision = match[0]
    opp = decision.get("opportunity_json") or {}
    token = opp.get("polymarket_token_id", "")

    live_price = broker.best_ask(token) if token else None
    ok, reason = validate_placeable(decision, now=utcnow(), live_price=live_price,
                                    tolerance=tolerance)
    if not ok:
        print(f"  NO colocable: {reason}")
        return

    order = build_trade_order_from_decision(decision, live_price)
    mode = "LIVE ⚠️" if broker.live else f"DRY-RUN ({broker._blocked_reason or 'flag off'})"
    print(f"\n  ── ORDEN A COLOCAR ({mode}) ──")
    print(f"    {opp.get('participant_home','?')} vs {opp.get('participant_away','?')}  "
          f"outcome={order.outcome}")
    print(f"    token={order.token_id[:18]}…  side={order.side.value}  "
          f"precio_live={order.price}  size={order.size_usdc} USDC  shares={order.size_shares}")
    expected = f"{to_decimal(order.size_usdc):.2f}"
    if not _confirm(expected, confirm):
        print("    Confirmación incorrecta — abortado, no se colocó nada.")
        return

    result = broker.place(order)
    if result.status != "error":
        client.mark_executed(full_key, result.model_dump(mode="json"))
    print(f"    → {result.status}  order_id={result.order_id}  raw={result.raw.get('note') or result.raw.get('error') or ''}")


def cmd_cancel(order_id: str, *, broker: PolymarketBroker, confirm: str | None) -> None:
    print(f"\n  Cancelar orden {order_id}")
    if not _confirm(order_id, confirm):
        print("    Confirmación incorrecta — abortado.")
        return
    result = broker.cancel(order_id)
    print(f"    → {result.status}  {result.raw.get('response') or result.raw.get('error') or ''}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Aprobar REVIEW → colocar / cancelar órdenes.")
    ap.add_argument("--state", default="data/agent_state.json")
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--approve", metavar="KEY", default=None)
    ap.add_argument("--cancel", metavar="ORDER_ID", default=None)
    ap.add_argument("--live", action="store_true", help="intenta envío REAL (requiere env-gates)")
    ap.add_argument("--tolerance", type=float, default=0.15)
    ap.add_argument("--confirm", default=None, help="valor de confirmación (no interactivo)")
    a = ap.parse_args()

    client = LocalStateClient(a.state, bankroll_usdc=a.bankroll)
    decisions = client._state.get("decisions", {})
    broker = PolymarketBroker(live=a.live)

    if a.approve:
        cmd_approve(a.approve, decisions=decisions, client=client, broker=broker,
                    tolerance=to_decimal(a.tolerance), confirm=a.confirm)
    elif a.cancel:
        cmd_cancel(a.cancel, broker=broker, confirm=a.confirm)
    else:
        cmd_list(decisions)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificación manual — list (sin crash)**

Run: `python scripts/orders.py --list`
Expected: imprime las REVIEWs pendientes (3 vencidas) y las órdenes abiertas live (o mensaje si no hay cuenta). Sin traceback ni crash de encoding, exit 0.

- [ ] **Step 3: Verificación manual — approve de una decisión vencida (dry-run)**

Run: `python scripts/orders.py --approve <key_de_una_review> --confirm 0`
(usar un prefijo de key real listado en el paso 2)
Expected: imprime `NO colocable: el evento ya empezó/terminó` y NO coloca nada (las 3 REVIEW actuales son de 2026-06-20). Exit 0, sin traceback.

- [ ] **Step 4: Verificación manual — cancel (dry-run, confirmación fallida)**

Run: `python scripts/orders.py --cancel ord-xyz --confirm no-coincide`
Expected: `Confirmación incorrecta — abortado.` (no llama al broker). Exit 0.

- [ ] **Step 5: Documentar y commit**

En `EXECUTION_GOLIVE.md`, bajo la lista de comandos de `## Correr (dry-run…)`, agregar:

```markdown
python scripts/orders.py --list                          # REVIEWs pendientes + órdenes abiertas live
python scripts/orders.py --approve <key> [--live]        # coloca la orden de una REVIEW (repricing + confirmación)
python scripts/orders.py --cancel <order_id> [--live]    # cancela una orden abierta
```

```bash
git add scripts/orders.py EXECUTION_GOLIVE.md
git commit -m "feat(orders): CLI aprobar REVIEW → place + cancel (doble gate + repricing)"
```

---

### Task 4: Suite completa verde

**Files:** ninguno (verificación).

- [ ] **Step 1: Correr la suite (excluyendo el test pre-existente time-dependent)**

Run: `python -m pytest -q --deselect tests/unit/test_adapters_football.py::test_db_reader_upcoming`
Expected: PASS — incluye los nuevos `test_broker_cancel` (2) y `test_review_order` (6).
(El test `test_db_reader_upcoming` es un fallo pre-existente dependiente de la hora, ajeno a B; se deselecciona a propósito.)

- [ ] **Step 2: Commit (si hubo ajustes)**

```bash
git add -A && git commit -m "test(orders): suite verde (subsistema B)" || echo "nada que commitear"
```

---

## Nota de verificación live (fuera de este plan)

Probar una colocación REAL requiere: (1) una decisión REVIEW **fresca** de un partido por
jugar (correr el pipeline sobre un fixture futuro, p. ej. `place_bets.py` en dry-run genera
REVIEWs), (2) `--live` + `POLYMARKET_LIVE=1` + key + kill-switch apagado, (3) teclear el
monto exacto para confirmar. Hacerlo sólo con OK explícito del usuario.
