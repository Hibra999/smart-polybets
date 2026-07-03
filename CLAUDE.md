# CLAUDE.md — Sports Quant Trading System (contexto global del repo)

Hedge fund sintético de un operador para mercados de predicción deportivos en
Polymarket. Claude actúa como analista cuantitativo, gestor de riesgo y operador;
el humano es el CIO que aprueba lo ambiguo y delega lo obvio.

## Principio rector
**Reproducibilidad hacia adelante**: cada decisión es el resultado determinístico
de inputs documentados procesados por funciones versionadas con contratos
explícitos (schemas Pydantic). Mismos inputs → misma decisión.

## Mapa del repo
| Carpeta | Rol |
|---|---|
| `core/` | utilidades compartidas, sin lógica de negocio (tipos, excepciones, strategy parser, `local_state`, `polymarket_client`, `timez`) |
| `data/` | un SQLite por torneo + DDL canónico por deporte (`_schema/`) |
| `adapters/` | única capa que lee los SQLite (read-only) + adapters de modelo (Elo, Bayes, TrueSkill, Poisson) |
| `venue/` | **única interfaz con Polymarket**: `gateway` (saldos/posiciones/órdenes/best_ask sobre el SDK), `discovery` (eventos vía SDK), `matching` (mapeo mercado↔partido) |
| `tournaments/` | config por torneo + `registry.py` + `STRATEGY.md` por estrategia |
| `signals/` | seam `SignalProvider` (modelo→señal), desacopla la estrategia del deporte |
| `research/` | produce `MarketOpportunity` con edge; `resolve_bet_market` elige lado/mercado (win / double_chance) |
| `risk/` | guardián: emite `RiskVerdict` (AUTO/REVIEW/DISCARD) aplicando el STRATEGY.md |
| `optimization/` | refina el sizing (cvxpy opcional, fallback Kelly) |
| `execution/` | construye y envía órdenes vía `venue/gateway` (dry-run por defecto; gates para live) |
| `portfolio/` | estado local (`LocalState`), idempotencia, PnL |
| `editorial/` | reportes en Markdown/HTML (no publica) |
| `agent/` | `tools/` (efectos), `workflows/`, `prompts/` |
| `tests/` | unit + integration |

## Reglas de oro (anti-deuda técnica)
1. **Schemas inmutables**: no modifiques in-place un schema usado por workflows aprobados; creá v2 y migrá.
2. **Functions puras**: si necesita estado o red, va en `agent/tools/`, `venue/gateway.py` o los loaders (`*_loader`), no en `functions/`.
3. **STRATEGY.md es la única fuente de reglas**: ningún threshold hardcodeado en Python (incl. `bet_type`, `side_criterion`, umbrales de edge, Kelly).
4. **Idempotency key en todo**: `hash(condition_id + outcome + strategy_id + strategy_version + date)`.
5. **Todo lo generado lleva `generated_at`, `tournament_id` y `strategy_version`**.
6. **`LocalState` (local) es la fuente de estado**: decisiones/órdenes/PnL viven en el estado local del repo; Polymarket se lee live vía `venue/gateway`.
7. **Una sola librería para Polymarket**: todo va por el SDK oficial a través de `venue/` (cero scrapers HTTP a Gamma).
8. **Almacenar en UTC, mostrar en local**: los tiempos se guardan en UTC; `core/timez` convierte para display (usuario en PDC/UTC-5; Polymarket etiqueta sus mercados en ET).

## Convención de documentación (hallazgos y mejoras) — para el futuro
**Todo hallazgo, gotcha, decisión o mejora de este proyecto se documenta EN ESTE MISMO REPO**
— nunca en memorias personales del agente ni en wikis externas. Dónde:
- Regla o comportamiento global → una sección en este `CLAUDE.md`.
- Algo específico de un área → el `SKILL.md`/`STRATEGY.md` de esa carpeta.
- Notas más largas → `docs/`.
Así el conocimiento viaja con el código y cualquier sesión/agente lo aplica al leer el repo.

**El proyecto debe ser idempotente.** Reejecutar un workflow con las mismas entradas no duplica
ni corrompe estado: misma entrada → misma decisión (principio rector) y misma escritura. Esto se
apoya en la idempotency key (Regla de oro #4), `generated_at`/`strategy_version` en todo lo generado,
y `check_idempotency()` antes de persistir. Cualquier mejora nueva debe preservar esta propiedad.

## Flujo
```
Research → Risk → Optimization → Execution → Portfolio → Editorial
```
(Los SKILL.md ubican Optimization después de Risk; ese es el orden de los workflows.)

## Reportar PnL / cuenta (¿cómo voy? / ¿cuál es mi PnL?)
La **fuente de verdad es la cuenta LIVE de Polymarket, NO el ledger local**. El estado local
(`data/agent_state.json`, vía `scripts/portfolio.py`) suele estar desincronizado — muestra 0
trades / PnL +0.00 porque las apuestas se ejecutaron fuera del agente.
```bash
python scripts/account.py --closed 300 --json     # solo lectura; requiere .[live] + POLYMARKET_PRIVATE_KEY
```
Al reportar, mostrar **siempre**:
1. **Equity total = cash + Σ(shares × current_price de posiciones abiertas)**. `balance.usdc_balance`
   es SOLO cash (colateral pUSD) — **no** suma las posiciones abiertas; hay que sumarlas a mano
   (no hay campo de equity directo).
2. Posiciones abiertas (mark-to-market + uPnL).
3. Histórico resuelto: lista ganados/perdidos, record W-L y PnL neto.

Una sola wallet: `POLYMARKET_FUNDER` (proxy, sig type 2). `scripts/account.py --reconcile` solo ajusta
el bankroll local al cash real; **no** importa las posiciones al ledger.

## Setup rápido
```bash
pip install -e ".[dev]"           # o: uv pip install -e ".[dev]"
python scripts/build_db.py --tournament fifa_world_cup_2026 --sport football
pytest
```

## Estado de integraciones (ver decisiones de alcance)
- **Estado (`LocalState`)**: decisiones, órdenes y PnL viven en el estado local del repo
  (`core/local_state.py`) — **Django fue retirado**. Polymarket (saldos/posiciones/mercados) se lee
  live vía `venue/gateway`.
- **Polymarket CLOB V2 (live)**: cableado vía `venue/gateway` sobre el **SDK oficial `polymarket-client`**
  (extra `.[live]`, `pip install --pre polymarket-client`). **Una sola librería** (no `py-clob-client`,
  no scraper Gamma — todo va por el SDK). El SDK V2 **deriva solo** el proxy wallet y el colateral **pUSD**,
  así que `funder`/`signature_type` son opcionales — basta la private key. Ejecución real **gateada**:
  `--live` + `POLYMARKET_LIVE=1` + key + kill-switch off + confirmación tipeada; **dry-run por defecto**.
  Ver `.env.example`.
- **Modelos Elo+Bayes+TrueSkill**: **migrados de `pypro_worldcup_betting`** (reales, puros) en
  `adapters/football/wc_models.py` + `wc_trueskill.py` + `wc_pipeline.py`. TrueSkill es un port
  1v1 puro validado contra la lib original (1e-5). Los 4 criterios (elo/bayes/blend/trueskill) operan.
- **Estrategia worldcup**: migrada (blend+Kelly) → `match_winner_wc_v1` (activa para FIFA WC 2026).
  `bet_type` selecciona el modo: `win` (apostar el pick a ganar) o `double_chance` (apostar a que el
  rival NO gana = 1X a 90', preciado por el modelo **Poisson**). Ver `STRATEGY_MIGRATION.md`.
- **Cuotas reales**: `scripts/migrate_worldcup_data.py` migra datos + 404 cuotas (Polymarket/Codere);
  `research.SqliteOddsSource` las expone como mercados. CLOB API live = mismo interfaz (pendiente).
- **Datos**: `scripts/migrate_worldcup_data.py` puebla el SQLite del Mundial 2026 desde `worldcup.db`.
