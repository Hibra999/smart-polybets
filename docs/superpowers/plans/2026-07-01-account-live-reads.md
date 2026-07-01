# Cuenta / lecturas live (subsistema A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar al agente visibilidad live de la cuenta de Polymarket (saldo pUSD, posiciones con mark-to-market, órdenes abiertas) más un comando de reconciliación explícito contra el ledger local, todo como tools deterministas.

**Architecture:** Fuente inyectable con stub por defecto (patrón `PolymarketLiveSource`/`PolymarketBroker`): un `AccountSource` (Protocol) que consume la lógica pura (`mark_to_market`, `tag_positions`, `reconcile`), y un adapter live `PolymarketAccountSource` (SDK V2 + private key) como borde delgado. La lógica se testea con fakes; el adapter se activa al instalar `.[live]` + key.

**Tech Stack:** Python 3.11+, Pydantic v2 (frozen), pytest, `requests` (ya dependencia). SDK live: `polymarket-client` (beta, no instalado localmente).

## Global Constraints

- Schemas Pydantic **frozen** (`ConfigDict(frozen=True)`), como el resto del repo.
- Funciones puras en `functions/` (sin estado ni red); el borde con red/SDK va en el adapter o el script.
- Las lecturas **NO** dependen de `POLYMARKET_LIVE` ni del kill-switch (son read-only); solo el adapter live requiere la private key.
- Decimales con `Decimal` y `core.utils.to_decimal`; nada de `float` en dinero.
- Consola: los scripts llaman `core.console.enable_utf8()` tras el `sys.path.insert`.
- El repo **no está bajo git**. Task 0 lo inicializa; si se omite, saltar los pasos de "Commit".
- Ejecutar tests con `python -m pytest` desde la raíz del repo.

---

### Task 0: Inicializar git (recomendado, habilita commits del plan)

**Files:**
- Create: `.gitignore` ya existe (no tocar).

- [ ] **Step 1: Inicializar repo y primer commit**

```bash
cd /c/0_documentos/gits/pypro/pypro_polymarket_agent
git init
git add -A
git commit -m "chore: baseline antes del subsistema A (cuenta live)"
```

Si prefieres no usar git, omite este task y todos los pasos "Commit" siguientes.

---

### Task 1: Schemas de cuenta live

**Files:**
- Create: `portfolio/schemas/account.py`
- Test: `tests/unit/test_account_schemas.py`

**Interfaces:**
- Produces: `AccountBalance(usdc_balance: Decimal, as_of: datetime, address: str | None)`;
  `LivePosition(condition_id, token_id, outcome, size_shares: Decimal, avg_entry_price: Decimal, current_price: Decimal | None, event_id, tournament_id, strategy_id)` con propiedades `unrealized_pnl -> Decimal | None` y `market_value -> Decimal | None`;
  `OpenOrder(order_id, condition_id, token_id, side, price: Decimal, size_shares: Decimal, size_matched: Decimal, status, created_at: datetime | None, event_id, tournament_id, strategy_id)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_account_schemas.py
from decimal import Decimal

from portfolio.schemas.account import LivePosition


def test_unrealized_pnl_none_without_price():
    p = LivePosition(condition_id="0xabc", token_id="1", outcome="YES",
                     size_shares=Decimal("100"), avg_entry_price=Decimal("0.50"))
    assert p.current_price is None
    assert p.unrealized_pnl is None
    assert p.market_value is None


def test_unrealized_pnl_and_market_value_with_price():
    p = LivePosition(condition_id="0xabc", token_id="1", outcome="YES",
                     size_shares=Decimal("100"), avg_entry_price=Decimal("0.50"),
                     current_price=Decimal("0.60"))
    assert p.unrealized_pnl == Decimal("10.0")   # (0.60-0.50)*100
    assert p.market_value == Decimal("60.0")      # 0.60*100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_account_schemas.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'portfolio.schemas.account'`.

- [ ] **Step 3: Write minimal implementation**

```python
# portfolio/schemas/account.py
"""Schemas de la cuenta live de Polymarket (wallet + CLOB). Frozen."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AccountBalance(BaseModel):
    model_config = ConfigDict(frozen=True)

    usdc_balance: Decimal          # colateral pUSD disponible
    as_of: datetime
    address: str | None = None


class LivePosition(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition_id: str
    token_id: str
    outcome: str
    size_shares: Decimal
    avg_entry_price: Decimal        # precio medio de entrada (0-1)
    current_price: Decimal | None = None   # best_bid live (valor de salida)
    event_id: str | None = None
    tournament_id: str | None = None
    strategy_id: str | None = None

    @property
    def unrealized_pnl(self) -> Decimal | None:
        if self.current_price is None:
            return None
        return (self.current_price - self.avg_entry_price) * self.size_shares

    @property
    def market_value(self) -> Decimal | None:
        if self.current_price is None:
            return None
        return self.current_price * self.size_shares


class OpenOrder(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    condition_id: str
    token_id: str
    side: str                       # "BUY" | "SELL"
    price: Decimal
    size_shares: Decimal
    size_matched: Decimal = Decimal("0")
    status: str = "open"
    created_at: datetime | None = None
    event_id: str | None = None
    tournament_id: str | None = None
    strategy_id: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_account_schemas.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add portfolio/schemas/account.py tests/unit/test_account_schemas.py
git commit -m "feat(account): schemas AccountBalance/LivePosition/OpenOrder"
```

---

### Task 2: Excepción + AccountSource (Protocol) + adapter SDK V2 (borde delgado)

**Files:**
- Modify: `core/exceptions.py` (agregar `AccountUnavailableError`)
- Create: `portfolio/functions/account_source.py`
- Test: `tests/unit/test_account_source.py`

**Interfaces:**
- Consumes: schemas de Task 1.
- Produces: `AccountUnavailableError(RuntimeError)`;
  `AccountSource` (Protocol) con `get_balance() -> AccountBalance`, `get_positions() -> list[LivePosition]`, `get_open_orders() -> list[OpenOrder]`;
  `PolymarketAccountSource(private_key: str | None = None, funder: str | None = None)` que lanza `AccountUnavailableError` mientras el SDK no esté instalado/wired.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_account_source.py
import pytest

from core.exceptions import AccountUnavailableError
from portfolio.functions.account_source import PolymarketAccountSource


def test_adapter_raises_when_sdk_absent():
    # Con una key presente pero el SDK live no instalado (estado actual del entorno),
    # cualquier lectura debe fallar con AccountUnavailableError (mensaje accionable).
    src = PolymarketAccountSource(private_key="0xdeadbeef")
    with pytest.raises(AccountUnavailableError):
        src.get_balance()


def test_adapter_raises_when_key_missing(monkeypatch):
    monkeypatch.delenv("POLYMARKET_PRIVATE_KEY", raising=False)
    src = PolymarketAccountSource(private_key=None)
    with pytest.raises(AccountUnavailableError):
        src.get_positions()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_account_source.py -v`
Expected: FAIL con `ImportError`/`ModuleNotFoundError` (aún no existe `account_source`) o `AttributeError` de `AccountUnavailableError`.

- [ ] **Step 3: Write minimal implementation**

Agregar al final de `core/exceptions.py`:

```python
class AccountUnavailableError(RuntimeError):
    """La cuenta live de Polymarket no está disponible (SDK no instalado o falta key)."""
```

Crear `portfolio/functions/account_source.py`:

```python
"""Fuente de cuenta live de Polymarket. Adapter SDK V2 detrás de un Protocol.

Patrón stub-inyectable (como research.PolymarketLiveSource / execution.PolymarketBroker):
la lógica pura consume el Protocol y se testea con un fake; el adapter real
`PolymarketAccountSource` es el borde delgado que requiere el SDK oficial V2
(`polymarket-client`) + private key. Sin ellos, lanza AccountUnavailableError.
"""
from __future__ import annotations

import os
from typing import Protocol

from core.exceptions import AccountUnavailableError
from portfolio.schemas.account import AccountBalance, LivePosition, OpenOrder


class AccountSource(Protocol):
    def get_balance(self) -> AccountBalance: ...
    def get_positions(self) -> list[LivePosition]: ...
    def get_open_orders(self) -> list[OpenOrder]: ...


class PolymarketAccountSource:
    """Adapter live: lee la cuenta vía el SDK oficial V2 (polymarket-client)."""

    def __init__(self, *, private_key: str | None = None, funder: str | None = None) -> None:
        self._private_key = private_key if private_key is not None else (
            os.getenv("POLYMARKET_PRIVATE_KEY") or ""
        )
        self._funder = funder or os.getenv("POLYMARKET_FUNDER") or None
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        if not self._private_key:
            raise AccountUnavailableError(
                "Falta POLYMARKET_PRIVATE_KEY para leer la cuenta live."
            )
        try:
            import polymarket_client  # noqa: F401  # TODO(wiring-sdk): confirmar nombre real
        except ImportError as exc:
            raise AccountUnavailableError(
                'SDK live no instalado. Corre: pip install --pre -e ".[live]"'
            ) from exc
        # TODO(wiring-sdk): construir el cliente V2 real con self._private_key/self._funder.
        raise AccountUnavailableError("Adapter SDK V2 pendiente de wiring (TODO).")

    def get_balance(self) -> AccountBalance:
        self._ensure_client()
        raise NotImplementedError  # TODO(wiring-sdk)

    def get_positions(self) -> list[LivePosition]:
        self._ensure_client()
        raise NotImplementedError  # TODO(wiring-sdk)

    def get_open_orders(self) -> list[OpenOrder]:
        self._ensure_client()
        raise NotImplementedError  # TODO(wiring-sdk)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_account_source.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add core/exceptions.py portfolio/functions/account_source.py tests/unit/test_account_source.py
git commit -m "feat(account): AccountSource protocol + adapter SDK V2 (stub/raise)"
```

---

### Task 3: Lógica pura — mark_to_market, tagging y reconcile

**Files:**
- Create: `portfolio/functions/account_reconcile.py`
- Test: `tests/unit/test_account_reconcile.py`

**Interfaces:**
- Consumes: schemas de Task 1.
- Produces:
  `index_decisions_by_condition(decisions: list[dict]) -> dict[str, dict]`;
  `mark_to_market(positions: list[LivePosition], price_of: Callable[[LivePosition], Decimal | None]) -> list[LivePosition]`;
  `tag_positions(positions: list[LivePosition], decisions: list[dict]) -> list[LivePosition]`;
  `reconcile(decisions: list[dict], balance: AccountBalance, positions: list[LivePosition], *, bankroll_param) -> dict` con claves `bankroll_param, balance_real, bankroll_delta, n_live_positions, n_executed_local, missing_fills, external_positions, as_of`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_account_reconcile.py
from datetime import datetime, timezone
from decimal import Decimal

from portfolio.functions.account_reconcile import (
    index_decisions_by_condition,
    mark_to_market,
    reconcile,
    tag_positions,
)
from portfolio.schemas.account import AccountBalance, LivePosition


def _pos(cid, token="1", entry="0.50", shares="100"):
    return LivePosition(condition_id=cid, token_id=token, outcome="YES",
                        size_shares=Decimal(shares), avg_entry_price=Decimal(entry))


def _dec(cid, event_id="wc_1", status="executed"):
    return {
        "condition_id": cid,
        "tournament_id": "fifa_world_cup_2026",
        "strategy_id": "match_winner_wc_v1",
        "status": status,
        "opportunity_json": {"event_id": event_id, "polymarket_condition_id": cid},
    }


def test_mark_to_market_sets_price_and_derives_pnl():
    marked = mark_to_market([_pos("0xa")], price_of=lambda p: Decimal("0.60"))
    assert marked[0].current_price == Decimal("0.60")
    assert marked[0].unrealized_pnl == Decimal("10.0")


def test_mark_to_market_leaves_none_when_no_price():
    marked = mark_to_market([_pos("0xa")], price_of=lambda p: None)
    assert marked[0].current_price is None
    assert marked[0].unrealized_pnl is None


def test_tag_positions_maps_known_and_leaves_external():
    positions = [_pos("0xa"), _pos("0xEXT")]
    tagged = tag_positions(positions, [_dec("0xa", event_id="wc_49")])
    by_cid = {p.condition_id: p for p in tagged}
    assert by_cid["0xa"].event_id == "wc_49"
    assert by_cid["0xa"].tournament_id == "fifa_world_cup_2026"
    assert by_cid["0xEXT"].event_id is None       # externa


def test_index_by_condition_reads_both_shapes():
    idx = index_decisions_by_condition([
        {"condition_id": "0xa"},
        {"opportunity_json": {"polymarket_condition_id": "0xb"}},
    ])
    assert set(idx) == {"0xa", "0xb"}


def test_reconcile_reports_delta_missing_fills_and_external():
    balance = AccountBalance(usdc_balance=Decimal("1200"),
                             as_of=datetime(2026, 7, 1, tzinfo=timezone.utc))
    decisions = [_dec("0xIN"), _dec("0xNOFILL")]   # dos ejecutadas locales
    positions = [_pos("0xIN"), _pos("0xEXT")]      # una casa, otra es externa
    rep = reconcile(decisions, balance, positions, bankroll_param=Decimal("1000"))
    assert rep["bankroll_delta"] == Decimal("200")
    assert rep["missing_fills"] == ["0xNOFILL"]    # ejecutada local sin posición on-chain
    assert rep["external_positions"] == ["0xEXT"]  # posición on-chain sin decisión local
    assert rep["n_live_positions"] == 2
    assert rep["n_executed_local"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_account_reconcile.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'portfolio.functions.account_reconcile'`.

- [ ] **Step 3: Write minimal implementation**

```python
# portfolio/functions/account_reconcile.py
"""Lógica pura de cuenta: indexado, mark-to-market, tagging y reconciliación.

Sin red ni SDK: recibe posiciones/orders (de un AccountSource) y las decisiones del
estado local. La escritura (ajuste de bankroll) la hace el script bajo --reconcile.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from core.utils import to_decimal
from portfolio.schemas.account import AccountBalance, LivePosition

PriceOf = Callable[[LivePosition], "Decimal | None"]


def _condition_of(decision: dict) -> str | None:
    return decision.get("condition_id") or (
        decision.get("opportunity_json") or {}
    ).get("polymarket_condition_id")


def index_decisions_by_condition(decisions: list[dict]) -> dict[str, dict]:
    """{condition_id -> primera decisión con ese condition_id}."""
    idx: dict[str, dict] = {}
    for d in decisions:
        cid = _condition_of(d)
        if cid:
            idx.setdefault(cid, d)
    return idx


def mark_to_market(positions: list[LivePosition], price_of: PriceOf) -> list[LivePosition]:
    """Devuelve copias con current_price poblado (best_bid live); unrealized_pnl deriva."""
    out: list[LivePosition] = []
    for p in positions:
        price = price_of(p)
        out.append(p.model_copy(update={"current_price": price})
                   if price is not None else p)
    return out


def tag_positions(positions: list[LivePosition], decisions: list[dict]) -> list[LivePosition]:
    """Etiqueta event/tournament/strategy por condition_id; deja None si no mapea."""
    idx = index_decisions_by_condition(decisions)
    out: list[LivePosition] = []
    for p in positions:
        d = idx.get(p.condition_id)
        if d is None:
            out.append(p)
            continue
        opp = d.get("opportunity_json") or {}
        out.append(p.model_copy(update={
            "event_id": opp.get("event_id"),
            "tournament_id": d.get("tournament_id"),
            "strategy_id": d.get("strategy_id"),
        }))
    return out


def reconcile(
    decisions: list[dict],
    balance: AccountBalance,
    positions: list[LivePosition],
    *,
    bankroll_param: Decimal | float,
) -> dict[str, Any]:
    """Compara realidad on-chain vs ledger local → reporte de drift (no escribe)."""
    bankroll_param = to_decimal(bankroll_param)
    live_cids = {p.condition_id for p in positions}
    executed = [d for d in decisions if d.get("status") == "executed"]
    exec_cids = {_condition_of(d) for d in executed}
    exec_cids.discard(None)

    return {
        "bankroll_param": bankroll_param,
        "balance_real": balance.usdc_balance,
        "bankroll_delta": balance.usdc_balance - bankroll_param,
        "n_live_positions": len(positions),
        "n_executed_local": len(executed),
        "missing_fills": sorted(exec_cids - live_cids),
        "external_positions": sorted(live_cids - exec_cids),
        "as_of": balance.as_of.isoformat(),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_account_reconcile.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add portfolio/functions/account_reconcile.py tests/unit/test_account_reconcile.py
git commit -m "feat(account): mark-to-market, tagging y reconcile (puros)"
```

---

### Task 4: Tools de cuenta (snapshot determinista)

**Files:**
- Create: `agent/tools/account_tools.py`
- Test: `tests/unit/test_account_tools.py`

**Interfaces:**
- Consumes: `AccountSource` (Task 2), schemas (Task 1), funciones de Task 3.
- Produces:
  `get_balance(source) -> AccountBalance`;
  `get_positions(source, *, price_of=None, decisions=None) -> list[LivePosition]`;
  `get_open_orders(source, *, decisions=None) -> list[OpenOrder]`;
  `account_snapshot(source, *, price_of=None, decisions=None) -> dict` con claves `balance`, `positions`, `open_orders`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_account_tools.py
from datetime import datetime, timezone
from decimal import Decimal

from agent.tools import account_tools
from portfolio.schemas.account import AccountBalance, LivePosition, OpenOrder


class FakeSource:
    def get_balance(self):
        return AccountBalance(usdc_balance=Decimal("1000"),
                              as_of=datetime(2026, 7, 1, tzinfo=timezone.utc))

    def get_positions(self):
        return [LivePosition(condition_id="0xa", token_id="1", outcome="YES",
                             size_shares=Decimal("100"), avg_entry_price=Decimal("0.50"))]

    def get_open_orders(self):
        return [OpenOrder(order_id="o1", condition_id="0xa", token_id="1",
                          side="BUY", price=Decimal("0.55"), size_shares=Decimal("20"))]


def _decisions():
    return [{"condition_id": "0xa", "tournament_id": "fifa_world_cup_2026",
             "strategy_id": "match_winner_wc_v1", "status": "executed",
             "opportunity_json": {"event_id": "wc_49", "polymarket_condition_id": "0xa"}}]


def test_snapshot_tags_and_marks():
    snap = account_tools.account_snapshot(
        FakeSource(), price_of=lambda p: Decimal("0.60"), decisions=_decisions())
    pos = snap["positions"][0]
    assert pos.event_id == "wc_49"                 # tagged
    assert pos.unrealized_pnl == Decimal("10.0")   # marked
    assert snap["open_orders"][0].event_id == "wc_49"
    assert snap["balance"].usdc_balance == Decimal("1000")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_account_tools.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'agent.tools.account_tools'`.

- [ ] **Step 3: Write minimal implementation**

```python
# agent/tools/account_tools.py
"""Tools de cuenta live: snapshot determinista para el agente. Inyecta AccountSource."""
from __future__ import annotations

from typing import Any

from portfolio.functions.account_reconcile import (
    index_decisions_by_condition,
    mark_to_market,
    tag_positions,
)
from portfolio.functions.account_source import AccountSource
from portfolio.schemas.account import AccountBalance, LivePosition, OpenOrder


def get_balance(source: AccountSource) -> AccountBalance:
    return source.get_balance()


def get_positions(source: AccountSource, *, price_of=None,
                  decisions: list[dict] | None = None) -> list[LivePosition]:
    positions = source.get_positions()
    if decisions:
        positions = tag_positions(positions, decisions)
    if price_of is not None:
        positions = mark_to_market(positions, price_of)
    return positions


def get_open_orders(source: AccountSource, *,
                    decisions: list[dict] | None = None) -> list[OpenOrder]:
    orders = source.get_open_orders()
    if not decisions:
        return orders
    idx = index_decisions_by_condition(decisions)
    out: list[OpenOrder] = []
    for o in orders:
        d = idx.get(o.condition_id)
        if d is None:
            out.append(o)
            continue
        opp = d.get("opportunity_json") or {}
        out.append(o.model_copy(update={
            "event_id": opp.get("event_id"),
            "tournament_id": d.get("tournament_id"),
            "strategy_id": d.get("strategy_id"),
        }))
    return out


def account_snapshot(source: AccountSource, *, price_of=None,
                     decisions: list[dict] | None = None) -> dict[str, Any]:
    return {
        "balance": get_balance(source),
        "positions": get_positions(source, price_of=price_of, decisions=decisions),
        "open_orders": get_open_orders(source, decisions=decisions),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_account_tools.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add agent/tools/account_tools.py tests/unit/test_account_tools.py
git commit -m "feat(account): tools get_balance/positions/open_orders/snapshot"
```

---

### Task 5: LocalStateClient — persistir y preferir el bankroll reconciliado

**Files:**
- Modify: `core/local_state.py`
- Test: `tests/unit/test_local_state_bankroll.py`

**Interfaces:**
- Produces: `LocalStateClient.set_bankroll(value: Decimal | float) -> None` (persiste `bankroll_usdc` en el estado, actualiza `initial_bankroll` y guarda). Al construir, si el estado ya tiene `bankroll_usdc`, se usa como `initial_bankroll` (la realidad reconciliada manda sobre el seed `--bankroll`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_local_state_bankroll.py
from decimal import Decimal

from core.local_state import LocalStateClient


def test_set_bankroll_persists_and_is_preferred_on_reload(tmp_path):
    p = tmp_path / "state.json"
    c1 = LocalStateClient(p, bankroll_usdc=1000.0)
    c1.set_bankroll(Decimal("1234.56"))
    assert c1.initial_bankroll == Decimal("1234.56")
    # Nueva instancia con otro seed: debe preferir el bankroll persistido.
    c2 = LocalStateClient(p, bankroll_usdc=1000.0)
    assert c2.initial_bankroll == Decimal("1234.56")
    assert c2.get_portfolio_state()["bankroll_usdc"] == "1234.56"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_local_state_bankroll.py -v`
Expected: FAIL con `AttributeError: 'LocalStateClient' object has no attribute 'set_bankroll'`.

- [ ] **Step 3: Write minimal implementation**

En `core/local_state.py`, reemplazar el cuerpo del `__init__` (las tres líneas que fijan `path`, `initial_bankroll` y `_state`):

```python
    def __init__(self, path: str | Path = "data/agent_state.json",
                 bankroll_usdc: float = 1000.0) -> None:
        self.path = Path(path)
        self._state = self._load()
        stored = self._state.get("bankroll_usdc")
        self.initial_bankroll = Decimal(str(stored if stored is not None else bankroll_usdc))
```

Y agregar el método (por ejemplo, junto a `mark_executed`):

```python
    def set_bankroll(self, value: Decimal | float) -> dict:
        """Persiste el bankroll (p. ej. tras reconciliar con el balance real)."""
        self._state["bankroll_usdc"] = str(value)
        self.initial_bankroll = Decimal(str(value))
        self._save()
        return {"bankroll_usdc": self._state["bankroll_usdc"]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_local_state_bankroll.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add core/local_state.py tests/unit/test_local_state_bankroll.py
git commit -m "feat(state): LocalStateClient.set_bankroll + preferir bankroll persistido"
```

---

### Task 6: CLI `scripts/account.py` (show + --reconcile + filtros)

**Files:**
- Create: `scripts/account.py`
- Modify: `EXECUTION_GOLIVE.md` (agregar el comando a la sección de dry-run)

**Interfaces:**
- Consumes: `account_tools` (Task 4), `PolymarketAccountSource` (Task 2), `reconcile` (Task 3), `core.local_state.LocalStateClient` + `set_bankroll` (Task 5), `core.console.enable_utf8`.

- [ ] **Step 1: Escribir el CLI**

```python
# scripts/account.py
#!/usr/bin/env python
"""Cuenta live de Polymarket en consola: saldo, posiciones y órdenes abiertas.

    python scripts/account.py                       # snapshot (todas las posiciones)
    python scripts/account.py --event wc_49         # filtra por evento
    python scripts/account.py --tournament fifa_world_cup_2026
    python scripts/account.py --reconcile           # drift vs estado local + ajusta bankroll
    python scripts/account.py --json

Requiere el SDK live (`pip install --pre -e ".[live]"`) + `POLYMARKET_PRIVATE_KEY`.
Sin ellos, informa que la cuenta live no está disponible (no rompe).
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from agent.tools import account_tools
from core.exceptions import AccountUnavailableError
from core.local_state import LocalStateClient
from portfolio.functions.account_reconcile import reconcile
from portfolio.functions.account_source import PolymarketAccountSource


def _dec(x) -> str:
    return f"{Decimal(str(x)):,.2f}"


def _pnl(x) -> str:
    return "   n/d" if x is None else f"{Decimal(str(x)):+,.2f}"


def _match_filter(tag_event, tag_tournament, event, tournament) -> bool:
    if event and tag_event != event:
        return False
    if tournament and tag_tournament != tournament:
        return False
    return True


def run(state_path: str, bankroll: float, event: str | None,
        tournament: str | None, do_reconcile: bool, as_json: bool) -> None:
    client = LocalStateClient(state_path, bankroll_usdc=bankroll)
    decisions = list(client._state.get("decisions", {}).values())
    source = PolymarketAccountSource()

    try:
        snap = account_tools.account_snapshot(source, price_of=None, decisions=decisions)
    except AccountUnavailableError as exc:
        print(f"\n  Cuenta live no disponible: {exc}")
        print('  (instala el extra live: pip install --pre -e ".[live]" y define POLYMARKET_PRIVATE_KEY)\n')
        return

    positions = [p for p in snap["positions"]
                 if _match_filter(p.event_id, p.tournament_id, event, tournament)]
    orders = [o for o in snap["open_orders"]
              if _match_filter(o.event_id, o.tournament_id, event, tournament)]
    balance = snap["balance"]

    if do_reconcile:
        rep = reconcile(decisions, balance, snap["positions"], bankroll_param=bankroll)
        if as_json:
            print(json.dumps(rep, indent=2, default=str))
        else:
            print(f"\n=== Reconciliación (as_of {rep['as_of']}) ===")
            print(f"    bankroll_param {_dec(rep['bankroll_param'])}  ·  "
                  f"balance real {_dec(rep['balance_real'])}  ·  "
                  f"delta {_pnl(rep['bankroll_delta'])}")
            print(f"    posiciones live {rep['n_live_positions']}  ·  "
                  f"ejecutadas local {rep['n_executed_local']}")
            if rep["missing_fills"]:
                print(f"    sin fill on-chain: {', '.join(rep['missing_fills'])}")
            if rep["external_positions"]:
                print(f"    externas (no en ledger): {', '.join(rep['external_positions'])}")
        # Única escritura: ajustar el bankroll local al balance real.
        client.set_bankroll(balance.usdc_balance)
        print(f"    bankroll local ajustado a {_dec(balance.usdc_balance)}\n")
        return

    if as_json:
        print(json.dumps({
            "balance": balance.model_dump(mode="json"),
            "positions": [p.model_dump(mode="json") for p in positions],
            "open_orders": [o.model_dump(mode="json") for o in orders],
        }, indent=2, default=str))
        return

    print(f"\n=== Cuenta Polymarket (as_of {balance.as_of.isoformat(timespec='minutes')}) ===")
    print(f"    saldo pUSD: {_dec(balance.usdc_balance)}")

    print(f"\n  ── POSICIONES ({len(positions)}) ─────────────────────────────────────")
    print(f"  {'EVENTO/COND':<20}{'OUT':<5}{'SHARES':>10}{'ENTRY':>7}{'PRICE':>7}{'uPnL':>10}")
    for p in positions:
        tag = p.event_id or (p.condition_id[:10] + "…")
        price = "  n/d" if p.current_price is None else f"{p.current_price:.2f}"
        print(f"  {str(tag)[:19]:<20}{p.outcome[:4]:<5}{p.size_shares:>10,.2f}"
              f"{p.avg_entry_price:>7.2f}{price:>7}{_pnl(p.unrealized_pnl):>10}")

    print(f"\n  ── ÓRDENES ABIERTAS ({len(orders)}) ──────────────────────────────────")
    print(f"  {'EVENTO/COND':<20}{'SIDE':<5}{'PRICE':>7}{'SIZE':>10}{'MATCHED':>10}")
    for o in orders:
        tag = o.event_id or (o.condition_id[:10] + "…")
        print(f"  {str(tag)[:19]:<20}{o.side[:4]:<5}{o.price:>7.2f}"
              f"{o.size_shares:>10,.2f}{o.size_matched:>10,.2f}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="Cuenta live de Polymarket (saldo/posiciones/órdenes).")
    ap.add_argument("--state", default="data/agent_state.json")
    ap.add_argument("--bankroll", type=float, default=1000.0)
    ap.add_argument("--event", default=None, help="filtra por event_id")
    ap.add_argument("--tournament", default=None, help="filtra por tournament_id")
    ap.add_argument("--reconcile", action="store_true", help="drift vs estado local + ajusta bankroll")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    run(a.state, a.bankroll, a.event, a.tournament, a.reconcile, a.json)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificación manual — cuenta no disponible (estado actual del entorno)**

Run: `python scripts/account.py`
Expected: imprime `Cuenta live no disponible: ...` + la sugerencia de instalar `.[live]`, **exit 0** (sin traceback, sin crash de encoding).

- [ ] **Step 3: Verificación manual — flags no rompen**

Run: `python scripts/account.py --json` y `python scripts/account.py --reconcile`
Expected: ambos terminan limpio con el mensaje de cuenta no disponible (aún no hay SDK/key).

- [ ] **Step 4: Documentar el comando**

En `EXECUTION_GOLIVE.md`, bajo la lista de comandos dry-run (donde ya está `portfolio.py`), agregar:

```markdown
python scripts/account.py                                # saldo, posiciones y órdenes live (requiere .[live]+key)
python scripts/account.py --reconcile                    # drift vs estado local + ajusta bankroll
```

- [ ] **Step 5: Commit**

```bash
git add scripts/account.py EXECUTION_GOLIVE.md
git commit -m "feat(account): CLI account.py (show + --reconcile + filtros por evento/torneo)"
```

---

### Task 7: Suite completa verde

**Files:** ninguno (verificación).

- [ ] **Step 1: Correr toda la suite**

Run: `python -m pytest -q`
Expected: PASS — los 115 previos + los nuevos (`test_account_schemas` 2, `test_account_source` 2, `test_account_reconcile` 5, `test_account_tools` 1, `test_local_state_bankroll` 1) = **126 passed**.

- [ ] **Step 2: Commit (si hubo ajustes)**

```bash
git add -A
git commit -m "test(account): suite completa verde (subsistema A)"
```

---

## Notas para el wiring live (fuera de este plan, cuando haya SDK + key)

Al instalar `pip install --pre -e ".[live]"` y definir `POLYMARKET_PRIVATE_KEY`, completar los `TODO(wiring-sdk)` en `PolymarketAccountSource`:
1. Confirmar el nombre real del paquete/import del SDK V2 y construir el cliente.
2. Mapear la respuesta del SDK a `AccountBalance`/`LivePosition`/`OpenOrder`.
3. Proveer un `price_of` real por `token_id` (endpoint público de precio del CLOB) y pasarlo al CLI para activar el mark-to-market.
Nada de la lógica pura ni de los tests cambia: el Protocol aísla el borde.
