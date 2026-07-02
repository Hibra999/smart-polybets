# Double-Chance Bet Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `bet_type: double_chance` strategy mode that bets the model pick's OPPONENT to NOT win (double-chance 1X = pick wins or draws at 90'), priced by the Poisson model.

**Architecture:** `pick_side` still selects the favorite. A new pure resolver `resolve_bet_market` decides which market/side to bet: `win` → pick's YES market; `double_chance` → opponent's NO market, with `model_probability = P(pick)+P(draw)` from Poisson. Both `scan_market.py` and `build_worldcup_opportunity` call the resolver so scan and orders stay consistent.

**Tech Stack:** Python 3.13, pydantic v2, pytest. Polymarket SDK via `venue/` gateway. Models in `adapters/football/`.

## Global Constraints

- Dinero real: sin `--live` + `POLYMARKET_LIVE=1` + key + kill-switch off + confirmación tipeada, todo es dry-run. Este feature NO relaja ningún gate.
- Todo Polymarket pasa por el SDK vía `venue/` (cero scrapers Gamma).
- Funciones puras testeables donde se pueda; el I/O (Poisson lee SQLite vía su loader) vive en la capa loader, no en `resolve_bet_market`.
- `bet_type` default = `"win"` → comportamiento idéntico al actual (backward-compatible).
- Constantes de lado: `HOME_WIN = "HOME_WIN"`, `AWAY_WIN = "AWAY_WIN"` (ya definidas en `research/functions/wc_strategy.py`).

---

### Task 1: `StrategyConfig.bet_type`

**Files:**
- Modify: `core/strategy.py` (field en `StrategyConfig`, validador, y set `_STR_KEYS`)
- Test: `tests/unit/test_strategy_parse.py` (o el test existente de parseo de StrategyConfig)

**Interfaces:**
- Produces: `StrategyConfig.bet_type: str` con valores `"win" | "double_chance"`, default `"win"`.

- [ ] **Step 1: Write the failing test**

En `tests/unit/test_strategy_parse.py` (crear si no existe; importar `StrategyConfig`):

```python
import pytest
from pydantic import ValidationError
from core.strategy import StrategyConfig

def _base(**over):
    d = dict(version="1", status="approved", tournament_id="t", sport="football",
             market_type="match_winner")
    d.update(over)
    return d

def test_bet_type_defaults_to_win():
    assert StrategyConfig(**_base()).bet_type == "win"

def test_bet_type_accepts_double_chance():
    assert StrategyConfig(**_base(bet_type="double_chance")).bet_type == "double_chance"

def test_bet_type_rejects_unknown():
    with pytest.raises(ValidationError):
        StrategyConfig(**_base(bet_type="parlay"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_strategy_parse.py -q`
Expected: FAIL (`bet_type` no existe / no valida).

- [ ] **Step 3: Implement**

En `core/strategy.py`, junto a `side_criterion` (línea ~89), añadir el campo:

```python
    bet_type: str = "win"          # win | double_chance (rival no gana = 1X a 90')
```

Añadir el validador junto a `_status_known`:

```python
    @field_validator("bet_type")
    @classmethod
    def _bet_type_known(cls, v: str) -> str:
        allowed = {"win", "double_chance"}
        if v not in allowed:
            raise ValueError(f"bet_type inválido: {v!r} (permitidos: {sorted(allowed)})")
        return v
```

Añadir `"bet_type"` al set `_STR_KEYS` (para que el parser del STRATEGY.md lo lea como string).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_strategy_parse.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/strategy.py tests/unit/test_strategy_parse.py
git commit -m "feat(strategy): campo bet_type (win|double_chance) en StrategyConfig"
```

---

### Task 2: Plomería del token NO (matching → PolymarketMarket → gateway)

**Files:**
- Modify: `venue/matching.py` (`_extract_yes_token` añade campos NO)
- Modify: `research/functions/market_scanner.py` (`PolymarketMarket` campos NO)
- Modify: `venue/gateway.py` (`find_match_markets` puebla los campos NO)
- Test: `tests/unit/test_gateway_matching.py` (o donde vivan los tests de matching)

**Interfaces:**
- Produces: `PolymarketMarket.no_token_id: str | None`, `.no_best_ask: Decimal | None`, `.no_probability: Decimal | None`. El dict de `_extract_yes_token` gana `"no_token_id"`, `"no_best_ask"`, `"no_price"`.

- [ ] **Step 1: Write the failing test**

En `tests/unit/test_gateway_matching.py`, añadir un test que arme un market fake con outcomes yes/no y verifique la extracción del NO. Reutilizar el patrón de fakes existente (SimpleNamespace). Ejemplo:

```python
from decimal import Decimal
from types import SimpleNamespace
from venue.matching import _extract_yes_token

def _mk():
    return SimpleNamespace(
        outcomes=SimpleNamespace(
            yes=SimpleNamespace(label="Yes", token_id="Y", price=Decimal("0.60")),
            no=SimpleNamespace(label="No", token_id="N", price=Decimal("0.40")),
        ),
        prices=SimpleNamespace(best_ask=Decimal("0.61"), best_bid=Decimal("0.59")),
        metrics=SimpleNamespace(volume_num=100, liquidity_num=50),
        state=SimpleNamespace(neg_risk=False, accepting_orders=True),
        trading=SimpleNamespace(minimum_tick_size=Decimal("0.001"), minimum_order_size=Decimal("5")),
        condition_id="c1",
    )

def test_extract_includes_no_side():
    info = _extract_yes_token(_mk())
    assert info["no_token_id"] == "N"
    assert info["no_price"] == Decimal("0.40")
    # NO ask = 1 - YES best_bid
    assert info["no_best_ask"] == Decimal("0.41")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_gateway_matching.py -q`
Expected: FAIL (`KeyError: 'no_token_id'`).

- [ ] **Step 3: Implement**

En `venue/matching.py::_extract_yes_token`, tras determinar `token_id`/`yes_price` del slot YES real, calcular el slot NO real (inverso) y añadir al dict devuelto:

```python
    # Slot NO real (inverso del YES). Si el YES estaba en outcomes.yes, el NO está
    # en outcomes.no, y viceversa (orden invertido).
    no_out = no_out if yes_label == "yes" else yes_out
    no_token_id = str(getattr(no_out, "token_id", "") or "")
    no_price = getattr(no_out, "price", None)
    no_price = Decimal(str(no_price)) if no_price is not None else (Decimal("1") - Decimal(str(yes_price)))
    # NO best_ask = 1 - (YES best_bid): comprar NO = alguien vende YES al bid.
    no_best_ask = (Decimal("1") - Decimal(str(best_bid))) if best_bid is not None else None
```

Y en el dict de retorno añadir:

```python
        "no_token_id": no_token_id,
        "no_best_ask": no_best_ask,
        "no_price": no_price,
```

En `research/functions/market_scanner.py::PolymarketMarket`, añadir tras `accepting_orders`:

```python
    # Lado NO del mismo mercado (para apuestas doble-oportunidad).
    no_token_id: str | None = None
    no_best_ask: Decimal | None = None
    no_probability: Decimal | None = None
```

En `venue/gateway.py::find_match_markets`, en el `PolymarketMarket(...)` (línea ~309) añadir:

```python
                    no_token_id=info.get("no_token_id"),
                    no_best_ask=info.get("no_best_ask"),
                    no_probability=info.get("no_price"),
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/unit/test_gateway_matching.py -q`
Expected: PASS. Correr también la suite completa para no romper el matching existente: `python -m pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add venue/matching.py research/functions/market_scanner.py venue/gateway.py tests/unit/test_gateway_matching.py
git commit -m "feat(venue): extraer y transportar el token NO de cada mercado"
```

---

### Task 3: `poisson_loader.match_result_probs`

**Files:**
- Create: `research/functions/poisson_loader.py`
- Test: `tests/unit/test_poisson_loader.py`

**Interfaces:**
- Produces: `match_result_probs(tournament_id: str, event_id: str) -> dict[str, float] | None` → `{"home","draw","away"}` (floats que suman ~1) o `None` si no hay fixture/forecast.

- [ ] **Step 1: Write the failing test**

`tests/unit/test_poisson_loader.py` — usar monkeypatch para inyectar un reader fake y un pipeline fake, sin tocar el SQLite:

```python
from research.functions import poisson_loader

class _FakeForecast:
    def prob_result(self, max_goals=10):
        return {"home": 0.5, "draw": 0.3, "away": 0.2}

class _FakePipe:
    def __init__(self, *a, **k): pass
    def fit(self): return self
    def forecast(self, home, away): return _FakeForecast()

class _FakeReader:
    def __init__(self, *a, **k): pass
    def get_fixture(self, eid):
        return {"home_team_id": "argentina", "away_team_id": "chile"} if eid == "wc_1" else None

def test_match_result_probs_ok(monkeypatch):
    poisson_loader._CACHE.clear()
    monkeypatch.setattr(poisson_loader, "_PIPELINE_CLS", _FakePipe)
    monkeypatch.setattr(poisson_loader, "_READER_CLS", _FakeReader)
    r = poisson_loader.match_result_probs("t", "wc_1")
    assert r == {"home": 0.5, "draw": 0.3, "away": 0.2}

def test_match_result_probs_no_fixture(monkeypatch):
    poisson_loader._CACHE.clear()
    monkeypatch.setattr(poisson_loader, "_PIPELINE_CLS", _FakePipe)
    monkeypatch.setattr(poisson_loader, "_READER_CLS", _FakeReader)
    assert poisson_loader.match_result_probs("t", "nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_poisson_loader.py -q`
Expected: FAIL (módulo no existe).

- [ ] **Step 3: Implement**

`research/functions/poisson_loader.py`:

```python
"""Carga de la probabilidad de resultado (1X2) del modelo Poisson para un fixture.

I/O aislado aquí (lee el SQLite vía el loader del Poisson y el fixture vía el reader).
Devuelve {"home","draw","away"} o None si no hay datos — no se inventa probabilidad.
El pipeline Poisson se cachea por tournament_id por proceso (fit es caro).
"""
from __future__ import annotations

from adapters.football.db_reader import FootballDBReader
from adapters.football.wc_poisson_pipeline import WorldCupPoissonPipeline

_PIPELINE_CLS = WorldCupPoissonPipeline   # indirección para tests
_READER_CLS = FootballDBReader
_CACHE: dict[str, object] = {}


def _pipeline(tournament_id: str):
    pipe = _CACHE.get(tournament_id)
    if pipe is None:
        pipe = _PIPELINE_CLS(tournament_id).fit()
        _CACHE[tournament_id] = pipe
    return pipe


def match_result_probs(tournament_id: str, event_id: str) -> dict[str, float] | None:
    try:
        fx = _READER_CLS(tournament_id).get_fixture(event_id)
        if fx is None:
            return None
        home_id, away_id = fx["home_team_id"], fx["away_team_id"]
        r = _pipeline(tournament_id).forecast(home_id, away_id).prob_result()
        total = float(r.get("home", 0)) + float(r.get("draw", 0)) + float(r.get("away", 0))
        if total <= 0:
            return None
        return {"home": float(r["home"]), "draw": float(r["draw"]), "away": float(r["away"])}
    except Exception:
        return None
```

Exportar en `research/functions/__init__.py`: añadir `from research.functions.poisson_loader import match_result_probs` y agregarlo a `__all__`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_poisson_loader.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add research/functions/poisson_loader.py research/functions/__init__.py tests/unit/test_poisson_loader.py
git commit -m "feat(research): poisson_loader.match_result_probs (1X2 de un fixture)"
```

---

### Task 4: `resolve_bet_market` + refactor de `build_worldcup_opportunity`

**Files:**
- Modify: `research/functions/wc_strategy.py`
- Test: `tests/unit/test_resolve_bet_market.py` (nuevo) y `tests/unit/test_worldcup_migration.py` (debe seguir pasando)

**Interfaces:**
- Consumes: `PolymarketMarket` (con campos NO de Task 2), `StrategyConfig.bet_type` (Task 1), poisson_result dict (Task 3).
- Produces:
  - `BetTarget` (frozen dataclass): `.market: PolymarketMarket`, `.model_probability: Decimal`.
  - `resolve_bet_market(pick_side: str, pick_model_prob: Decimal, markets: list[PolymarketMarket], strategy: StrategyConfig, poisson_result: dict | None) -> BetTarget | None`.
  - `build_worldcup_opportunity(prediction, markets, strategy, *, now=None, poisson_result=None)` (nuevo kwarg).

- [ ] **Step 1: Write the failing test**

`tests/unit/test_resolve_bet_market.py`:

```python
from decimal import Decimal
from research.functions.wc_strategy import resolve_bet_market, HOME_WIN, AWAY_WIN
from research.functions.market_scanner import PolymarketMarket
from core.strategy import StrategyConfig

def _mk(model_outcome, yes_prob, no_token="N", no_prob="0.0", no_ask="0.0"):
    return PolymarketMarket(
        condition_id="c", token_id="Y"+model_outcome, outcome="YES",
        model_outcome=model_outcome, market_probability=Decimal(yes_prob),
        volume_usdc=Decimal("100"), liquidity_usdc=Decimal("50"),
        no_token_id=no_token, no_probability=Decimal(no_prob), no_best_ask=Decimal(no_ask))

def _strat(bet_type):
    return StrategyConfig(version="1", status="approved", tournament_id="t",
                          sport="football", market_type="match_winner", bet_type=bet_type)

MARKETS = [_mk(HOME_WIN, "0.60"), _mk(AWAY_WIN, "0.25", no_token="No_away",
                                     no_prob="0.75", no_ask="0.76")]

def test_win_mode_picks_own_yes_market():
    t = resolve_bet_market(HOME_WIN, Decimal("0.60"), MARKETS, _strat("win"), None)
    assert t.market.model_outcome == HOME_WIN and t.market.outcome == "YES"
    assert t.model_probability == Decimal("0.60")

def test_double_chance_picks_opponent_no_market():
    # pick=HOME, rival=AWAY → compramos el NO del mercado AWAY
    pr = {"home": 0.55, "draw": 0.25, "away": 0.20}
    t = resolve_bet_market(HOME_WIN, Decimal("0.60"), MARKETS, _strat("double_chance"), pr)
    assert t.market.outcome == "NO"
    assert t.market.token_id == "No_away"
    assert t.market.model_outcome == HOME_WIN          # el NO resuelve a favor del pick
    # model_prob = P(home)+P(draw) = 0.80
    assert abs(float(t.model_probability) - 0.80) < 1e-9

def test_double_chance_skips_without_poisson():
    assert resolve_bet_market(HOME_WIN, Decimal("0.6"), MARKETS, _strat("double_chance"), None) is None

def test_double_chance_skips_without_no_token():
    mk = [_mk(HOME_WIN, "0.60"), PolymarketMarket(condition_id="c", token_id="Ya",
           outcome="YES", model_outcome=AWAY_WIN, market_probability=Decimal("0.25"),
           volume_usdc=Decimal("1"), liquidity_usdc=Decimal("1"))]  # sin no_token_id
    pr = {"home": 0.55, "draw": 0.25, "away": 0.20}
    assert resolve_bet_market(HOME_WIN, Decimal("0.6"), mk, _strat("double_chance"), pr) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_resolve_bet_market.py -q`
Expected: FAIL (`resolve_bet_market` no existe).

- [ ] **Step 3: Implement**

En `research/functions/wc_strategy.py`, añadir imports y el resolver:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class BetTarget:
    market: PolymarketMarket
    model_probability: Decimal


def resolve_bet_market(pick_side, pick_model_prob, markets, strategy, poisson_result):
    """Decide qué mercado/lado apostar. win → YES del pick; double_chance → NO del rival."""
    if strategy.bet_type == "double_chance":
        if poisson_result is None:
            return None
        opponent = AWAY_WIN if pick_side == HOME_WIN else HOME_WIN
        opp = next((m for m in markets if m.model_outcome == opponent), None)
        if opp is None or not opp.no_token_id:
            return None
        key = "home" if pick_side == HOME_WIN else "away"
        one_x = Decimal(str(poisson_result[key] + poisson_result["draw"]))
        no_market = opp.model_copy(update={
            "token_id": opp.no_token_id,
            "outcome": "NO",
            "model_outcome": pick_side,   # el NO resuelve a favor de "el pick no pierde"
            "market_probability": (opp.no_probability if opp.no_probability is not None
                                   else Decimal("1") - opp.market_probability),
            "best_ask": opp.no_best_ask,
        })
        return BetTarget(market=no_market, model_probability=one_x)

    # win (default)
    mk = next((m for m in markets if m.model_outcome == pick_side), None)
    if mk is None:
        return None
    return BetTarget(market=mk, model_probability=pick_model_prob)
```

Refactorizar `build_worldcup_opportunity` para usar el resolver y aceptar `poisson_result`:

```python
def build_worldcup_opportunity(prediction, markets, strategy, *, now=None,
                               poisson_result=None):
    pick = pick_side(prediction, strategy.side_criterion, strategy.blend_weight)
    if pick["appearance_no"] < strategy.warmup_match_no:
        return None
    if strategy.use_bayes_filter and pick["bayes_pick"] < strategy.bayes_threshold:
        return None
    target = resolve_bet_market(pick["side"], pick["model_prob"], markets, strategy,
                                poisson_result)
    if target is None:
        return None
    return calculate_edge(prediction, target.market, strategy, now=now,
                          model_probability=target.model_probability)
```

Exportar `resolve_bet_market` y `BetTarget` en `research/functions/__init__.py`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/unit/test_resolve_bet_market.py tests/unit/test_worldcup_migration.py -q`
Expected: PASS (los tests viejos de `build_worldcup_opportunity` en modo win siguen verdes porque `poisson_result` default None y `bet_type` default win).

- [ ] **Step 5: Commit**

```bash
git add research/functions/wc_strategy.py research/functions/__init__.py tests/unit/test_resolve_bet_market.py
git commit -m "feat(research): resolve_bet_market + double_chance en build_worldcup_opportunity"
```

---

### Task 5: Wiring de callers (scan_market + agent tools)

**Files:**
- Modify: `scripts/scan_market.py` (usar `resolve_bet_market` + `match_result_probs` + display)
- Modify: `agent/tools/research_tools.py` (pasar `poisson_result`)
- Modify: `agent/workflows/daily_suggestions.py` (pasar `poisson_result`)
- Test: `tests/unit/test_scan_market_dc.py` (nuevo, con fakes) — opcional pero recomendado

**Interfaces:**
- Consumes: `resolve_bet_market`, `BetTarget` (Task 4), `match_result_probs` (Task 3).

- [ ] **Step 1: Write the failing test (scan helper)**

Para testear sin gateway live, extraer la lógica de fila a un helper puro en `scripts/scan_market.py`:
`_bet_row(sig_side, sig_prob, markets, strategy, poisson_result) -> tuple[outcome, model_prob, market_prob, edge] | None` que internamente llama `resolve_bet_market`. Test:

```python
from decimal import Decimal
import scripts.scan_market as sm
from research.functions.market_scanner import PolymarketMarket
from core.strategy import StrategyConfig

def _strat(bt): return StrategyConfig(version="1", status="approved", tournament_id="t",
    sport="football", market_type="match_winner", bet_type=bt)

def test_bet_row_double_chance():
    markets = [PolymarketMarket(condition_id="c", token_id="Yh", outcome="YES",
                 model_outcome="HOME_WIN", market_probability=Decimal("0.6"),
                 volume_usdc=Decimal("1"), liquidity_usdc=Decimal("1")),
               PolymarketMarket(condition_id="c", token_id="Ya", outcome="YES",
                 model_outcome="AWAY_WIN", market_probability=Decimal("0.25"),
                 volume_usdc=Decimal("1"), liquidity_usdc=Decimal("1"),
                 no_token_id="Na", no_probability=Decimal("0.72"), no_best_ask=Decimal("0.73"))]
    pr = {"home": 0.55, "draw": 0.25, "away": 0.20}
    row = sm._bet_row("HOME_WIN", Decimal("0.6"), markets, _strat("double_chance"), pr)
    assert row is not None
    outcome, model_prob, market_prob, edge = row
    assert outcome == "NO"
    assert abs(float(model_prob) - 0.80) < 1e-9         # P(home)+P(draw)
    assert market_prob == Decimal("0.72")
    assert abs(float(edge) - 0.08) < 1e-9               # 0.80 - 0.72
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_scan_market_dc.py -q`
Expected: FAIL (`_bet_row` no existe).

- [ ] **Step 3: Implement**

En `scripts/scan_market.py`:

Añadir imports:
```python
from research.functions.wc_strategy import resolve_bet_market  # noqa: E402
from research.functions.poisson_loader import match_result_probs  # noqa: E402
```

Añadir el helper puro:
```python
def _bet_row(sig_side, sig_prob, markets, strategy, poisson_result):
    target = resolve_bet_market(sig_side, sig_prob, markets, strategy, poisson_result)
    if target is None:
        return None
    m = target.market
    return m.outcome, target.model_probability, m.market_probability, \
        target.model_probability - m.market_probability
```

Reemplazar la selección inline (el bloque `matched = next(... m.model_outcome == sig.side ...)` + `edge = sig.model_probability - matched.market_probability`) por:
```python
        poisson_result = (match_result_probs(tournament_id, fixture_id)
                          if strategy.bet_type == "double_chance" else None)
        bet = _bet_row(sig.side, sig.model_probability, markets, strategy, poisson_result)
        if bet is None:
            _skip(label, f"sin mercado apto para bet_type={strategy.bet_type}", as_json, rows)
            continue
        outcome_side, model_prob, market_prob, edge = bet
```
Y usar `outcome_side` (YES/NO), `model_prob`, `market_prob`, `edge` en la fila impresa y en el `row` dict. Añadir la etiqueta `[1X]` en la columna de PICK cuando `strategy.bet_type == "double_chance"` (ej. `f"{sig.side} [1X]"`). Nota: `strategy` debe estar disponible en el scope del loop (ya se carga con `load_active_strategy`; si no está en el scope local, pasarlo).

En `agent/tools/research_tools.py` (línea ~45), calcular y pasar `poisson_result`:
```python
        from research.functions.poisson_loader import match_result_probs
        poisson_result = (match_result_probs(strategy.tournament_id, prediction.event_id)
                          if strategy.bet_type == "double_chance" else None)
        opp = build_worldcup_opportunity(prediction, markets, strategy, now=now,
                                         poisson_result=poisson_result)
```

En `agent/workflows/daily_suggestions.py` (línea ~87), igual:
```python
        from research.functions.poisson_loader import match_result_probs
        poisson_result = (match_result_probs(strat.tournament_id, pred.event_id)
                          if strat.bet_type == "double_chance" else None)
        opp = build_worldcup_opportunity(pred, markets, strat, poisson_result=poisson_result)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/unit/test_scan_market_dc.py -q && python -m pytest -q`
Expected: PASS (suite completa verde).

- [ ] **Step 5: Commit**

```bash
git add scripts/scan_market.py agent/tools/research_tools.py agent/workflows/daily_suggestions.py tests/unit/test_scan_market_dc.py
git commit -m "feat: cablear double_chance en scan_market y agent tools (resolver compartido)"
```

---

### Task 6: Documentar `bet_type` en STRATEGY.md

**Files:**
- Modify: `tournaments/fifa_world_cup_2026/strategies/match_winner_wc_v1/STRATEGY.md`

**Interfaces:** ninguna (doc/config).

- [ ] **Step 1: Implement**

En la sección de parámetros del STRATEGY.md (junto a `side_criterion`), añadir la línea documentada, dejando el default `win` (no cambiamos el comportamiento sin pedido explícito):

```
bet_type: win        # win = apostar el pick a ganar | double_chance = apostar a que el rival NO gana (1X a 90', preciado por Poisson)
```

- [ ] **Step 2: Verify parse**

Run: `python -c "from tournaments.registry import load_active_strategy; print(load_active_strategy('fifa_world_cup_2026').bet_type)"`
Expected: imprime `win`.

- [ ] **Step 3: Commit**

```bash
git add tournaments/fifa_world_cup_2026/strategies/match_winner_wc_v1/STRATEGY.md
git commit -m "docs(strategy): documentar bet_type en STRATEGY.md del WC"
```

---

## Notas de integración final (post-tareas)

- Correr `python scripts/scan_market.py` (dry) con `bet_type: win` y confirmar que no cambió nada.
- Poner `bet_type: double_chance` en el STRATEGY.md y correr `scan_market` dry para ver las filas `[1X]` (outcome NO, edge del Poisson). Revertir a `win` si no se quiere dejar activo.
- La colocación real de la orden NO se ejecuta hasta que el usuario apruebe con los gates (`--live` etc.). Verificar que el broker compra `market.token_id` respetando `market.outcome` (si el broker asume YES, corregir en un fix aparte — fuera del alcance de este plan salvo que el review lo marque).
