# PEPA — especificación técnica

## Objetivo

PEPA transforma datos deportivos y precios de Polymarket en decisiones reproducibles
para dos mercados:

- `liga_mx_2026` — Liga MX Apertura 2026.
- `nfl_2026` — temporada NFL 2026.

Codex es el único agente soportado. El humano conserva el rol de CIO y toda decisión
ambigua o monetaria que requiera revisión.

## Arquitectura

```text
Research → Risk → Optimization → Execution → Portfolio → Editorial
```

El flujo es unidireccional. Cada etapa consume el contrato de la anterior y no llama
hacia atrás.

| Área | Responsabilidad | Salida principal |
|---|---|---|
| Research | modelo, mercado y edge | `MarketOpportunity` |
| Risk | límites y reglas cualitativas | `RiskVerdict` |
| Optimization | Kelly y topes | `SizingOutput` |
| Execution | precio, slippage y orden | `ExecutionDecision` / `OrderResult` |
| Portfolio | idempotencia, estado y PnL | `PortfolioState` |
| Editorial | reporte posterior | HTML/texto |

La lógica pura vive en `*/functions/`, los contratos Pydantic en `*/schemas/` y la
orquestación en `agent/workflows/`. `core/` contiene tipos y utilidades compartidas.

## Límites de integración

- Todo acceso a Polymarket pasa por `venue/PolymarketGateway`.
- Los adapters deportivos leen SQLite; no ejecutan órdenes.
- Los scripts orquestan; no duplican lógica de dominio.
- `LocalStateClient` persiste decisiones e idempotencia en JSON local.
- SQLite, estado local, `.env` y credenciales no se versionan.

## Datos

```text
data/
├── _schema/
│   ├── football.sql
│   └── american_football.sql
├── liga_mx_2026/
│   ├── DATA_SOURCES.md
│   └── ingest/
└── nfl_2026/
    ├── DATA_SOURCES.md
    └── ingest/
```

Cada torneo usa `data/<id>/<id>.sqlite`. Los IDs de fixture son deportivos y no son
`condition_id` de Polymarket.

## Modelos

### Liga MX

`FootballModelAdapter` combina:

- Elo con `home_adv_elo=80`;
- Bayes Beta-Bernoulli;
- TrueSkill;
- Poisson separado para 1X2/goles con `neutral_venue=False`.

La estrategia `match_winner_ligamx_v1` usa blend y Kelly fraccional, pero permanece
`draft`. Sólo se observa con `allow_draft`/`--observe-draft` y nunca live.

`theta_lay_v1` es una hipótesis intradía doc-only, también `draft`.

### NFL

`AmericanFootballTrueSkillAdapter` procesa juegos en orden cronológico y produce
probabilidad binaria. `game_winner_v1` está `approved`, aplica warmup, límites de
riesgo y Kelly fraccional. Aprobada no significa live: el broker es dry-run por
defecto.

## Registro

`tournaments/registry.py` es la lista cerrada de IDs, tags, fechas, adapters y
estrategias. `load_active_strategy(id)` sólo devuelve una estrategia aprobada;
`require_approved=False` está reservado a análisis explícito de drafts.

## Decisión

1. Research carga fixture, predicción y mercados.
2. Calcula `edge = p_modelo - p_mercado`.
3. Risk devuelve:
   - `AUTO`: puede avanzar;
   - `REVIEW`: espera al CIO;
   - `DISCARD`: se descarta;
   - `SKIP`: falta una precondición operativa.
4. Optimization aplica Kelly fraccional y topes.
5. Execution vuelve a consultar precio y valida slippage/tick/tamaño.
6. Portfolio comprueba idempotencia y persiste el resultado.
7. Editorial describe la decisión; publicar necesita otra autorización.

`AUTO` no implica dinero enviado. En dry-run el estado es `simulated`; sólo
`OrderResult.status == "live"` acredita ejecución.

## Codex

- `AGENTS.md` contiene reglas durables.
- `INIT.md` es el manual de arranque.
- `.agents/skills/pepa-help/SKILL.md` atiende “Codex, help”.
- `docs/PROMPTS.md` es el catálogo visible de solicitudes.
- `.codex/config.toml` ejecuta freshness en `SessionStart`.

Pedir ayuda sólo muestra documentación y no ejecuta acciones.

## Seguridad live

Los gates son acumulativos:

1. autorización concreta del usuario;
2. estrategia aprobada y veredicto no REVIEW;
3. freshness MONEY;
4. signer EVM válido;
5. `POLYMARKET_LIVE=1`;
6. `POLYMARKET_KILL_SWITCH=0`;
7. flag `--live`;
8. precio, slippage, tick, mínimo y allowance válidos;
9. confirmación tipada.

Ningún análisis, backtest, estado AUTO o prompt de ayuda sustituye estos gates.

## Verificación

```bash
.venv/bin/pip check
.venv/bin/pytest
.venv/bin/ruff check .
git diff --check
```

Las pruebas son deterministas y no usan red. Las ingestas y scans con red se validan
por separado y nunca se combinan con `--live` durante instalación.
