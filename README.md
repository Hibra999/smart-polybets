# Sports Quant Trading System

Un hedge fund sintético asistido por Claude para operar mercados de predicción
deportivos en Polymarket. Extensible a cualquier torneo o liga: el torneo activo
es configuración, no un supuesto hardcodeado.

> Implementación del whitepaper `spec.md` (v0.3). Ver `CLAUDE.md` para el contexto
> de operación y las reglas anti-deuda.

## Arquitectura

Tres pilares verticales por área: `functions/` (Python puro, testeable),
`schemas/` (contratos Pydantic) y `SKILL.md` (briefing para Claude).

Flujo unidireccional:

```
Research → Risk → Optimization → Execution → Portfolio → Editorial
```

El estado (decisiones, órdenes, PnL) vive en `LocalState` (estado local del repo);
Django fue retirado. Polymarket se lee live vía `venue/gateway` sobre el SDK oficial —
**una sola librería**, sin scrapers.

## Instalación

```bash
pip install -e ".[dev]"
# opcional, para optimización por batch:
pip install -e ".[optimize]"     # cvxpy
```

## Construir la base de datos de un torneo

Los `.sqlite` no se versionan (se construyen desde el DDL canónico), con UNA
excepción: los exports de mercado por evento (`data/<torneo>/events/*/ticks.sqlite`)
sí — son datasets finitos y cerrados para análisis.

```bash
python scripts/build_db.py --tournament fifa_world_cup_2026 --sport football
python scripts/build_db.py --tournament liga_mx_2026 --sport football
python scripts/build_db.py --tournament nfl_2026 --sport american_football
```

Luego se pueblan con los scripts de `data/{tournament_id}/ingest/`.

## Torneos registrados

| tournament_id | Estado | Estrategias |
|---|---|---|
| `fifa_world_cup_2026` | activo hasta 2026-07-19 | `match_winner_wc_v1` (approved) |
| `liga_mx_2026` (Apertura) | activo desde 2026-07-16, **modo observación** | `match_winner_ligamx_v1` (draft), `theta_lay_v1` (draft, trading — `docs/theta-trade-manual.md`) |
| `nfl_2026` | arranca 2026-09-06 | `game_winner_v1` |

## Tests

```bash
pytest
```

## Dos modos de operación de Claude

| Modo | Condición | Acción |
|---|---|---|
| **AUTO** | workflow aprobado + reglas cuantitativas satisfechas | ejecuta sin intervención |
| **REVIEW** | condición ambigua / componente cualitativo | redacta recomendación y espera aprobación |

## Estado de integraciones

| Pieza | Estado |
|---|---|
| Áreas, schemas, adapters, agent, workflows | implementado |
| Modelos Elo + Bayes + TrueSkill (football) | **migrados de `pypro_worldcup_betting`** (reales, puros) |
| Estrategia blend+Kelly (FIFA WC 2026) | migrada → `match_winner_wc_v1` (activa) |
| Cuotas / mercados Polymarket | live vía `venue/gateway` sobre el SDK (descubrimiento en `venue/discovery`) |
| Modelo Elo (NFL) | implementado (real) |
| Estrategia doble-oportunidad | `bet_type: double_chance` (rival no gana / 1X a 90', preciado por Poisson) |
| Polymarket CLOB V2 (órdenes) | cableado vía `venue/gateway` (SDK oficial `polymarket-client`); dry-run por defecto, live gateado |
| Estado | `LocalState` local (Django retirado); apuestas manuales por carril **CIO override** (`propose_bet.py`) con riesgo + ledger |
| Datos `.sqlite` | DDL + builder + `migrate_worldcup_data.py` (WC) + ingest Polymarket/football-data (Liga MX) |
| Datos de mercado en tiempo real | `record_market_ticks.py` (1 snapshot/min: precios + book depth + score live) |
| Trading intra-partido | theta trade (`theta_lay_v1` draft): monitor CLI con regla de salida + hard stop (`theta_monitor.py`) |

## Agregar un torneo nuevo

Ver `tournaments/README.md` (4 pasos, sin tocar el pipeline de áreas).
