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
| `core/` | utilidades compartidas, sin lógica de negocio (tipos, excepciones, django_client, strategy parser) |
| `data/` | un SQLite por torneo + DDL canónico por deporte (`_schema/`) |
| `adapters/` | única capa que lee los SQLite (read-only) + adapters de modelo (Elo) |
| `tournaments/` | config por torneo + `registry.py` + `STRATEGY.md` por estrategia |
| `research/` | produce `MarketOpportunity` con edge |
| `risk/` | guardián: emite `RiskVerdict` (AUTO/REVIEW/DISCARD) aplicando el STRATEGY.md |
| `optimization/` | refina el sizing (cvxpy opcional, fallback Kelly) |
| `execution/` | construye y envía órdenes (submit es STUB hasta wiring CLOB) |
| `portfolio/` | puente con el Django App (estado, idempotencia, PnL) |
| `editorial/` | reportes en Markdown (no publica) |
| `agent/` | `CLAUDE.md`, `HOOKS.md`, `tools/`, `workflows/`, `prompts/` |
| `tests/` | unit + integration |

## Reglas de oro (anti-deuda técnica)
1. **Schemas inmutables**: no modifiques in-place un schema usado por workflows aprobados; creá v2 y migrá.
2. **Functions puras**: si necesita estado o API, va en `agent/tools/` o `core/django_client.py`, no en `functions/`.
3. **STRATEGY.md es la única fuente de reglas**: ningún threshold hardcodeado en Python.
4. **Idempotency key en todo**: `hash(condition_id + outcome + strategy_id + strategy_version + date)`.
5. **Todo lo generado lleva `generated_at`, `tournament_id` y `strategy_version`**.
6. **El Django App es la única fuente de estado**: el repo no tiene DB propia ni cachea posiciones.

## Flujo
```
Research → Risk → Optimization → Execution → Portfolio → Editorial
```
(Los SKILL.md ubican Optimization después de Risk; ese es el orden de los workflows.)

## Setup rápido
```bash
pip install -e ".[dev]"           # o: uv pip install -e ".[dev]"
python scripts/build_db.py --tournament fifa_world_cup_2026 --sport football
pytest
```

## Estado de integraciones (ver decisiones de alcance)
- **Django App**: consumido vía `core/django_client.py` (HTTP). Los endpoints `/api/agent/`
  viven en el repo del Django App, fuera de este repo.
- **Polymarket CLOB V2**: `execution.submit_order` es STUB; wire el **SDK oficial `polymarket-client`**
  (extra `.[live]`, `pip install --pre polymarket-client`) para real. **Cambio de librería:** se
  reemplazó `py-clob-client` por `polymarket-client` (V2). Ya **NO se usan 2 APIs / 2 pasos de auth**:
  el SDK V2 **deriva solo** el proxy wallet y los contratos de colateral **pUSD**, así que `funder` y
  `signature_type` son opcionales (override) — basta la private key + `POLYMARKET_LIVE=1`. Ver `.env.example`.
- **Modelos Elo+Bayes+TrueSkill**: **migrados de `pypro_worldcup_betting`** (reales, puros) en
  `adapters/football/wc_models.py` + `wc_trueskill.py` + `wc_pipeline.py`. TrueSkill es un port
  1v1 puro validado contra la lib original (1e-5). Los 4 criterios (elo/bayes/blend/trueskill) operan.
- **Estrategia worldcup**: migrada (blend+Kelly) → `match_winner_wc_v1` (activa para FIFA WC 2026).
  Ver `tournaments/fifa_world_cup_2026/STRATEGY_MIGRATION.md`.
- **Cuotas reales**: `scripts/migrate_worldcup_data.py` migra datos + 404 cuotas (Polymarket/Codere);
  `research.SqliteOddsSource` las expone como mercados. CLOB API live = mismo interfaz (pendiente).
- **Datos**: `scripts/migrate_worldcup_data.py` puebla el SQLite del Mundial 2026 desde `worldcup.db`.
