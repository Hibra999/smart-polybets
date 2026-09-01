# PEPA — Liga MX y NFL en Polymarket

Sistema cuantitativo operado exclusivamente con Codex para investigar, probar y, con
autorización explícita, ejecutar estrategias sobre dos mercados: Liga MX y NFL.

## Arquitectura

Cada decisión recorre una sola dirección:

```text
Research → Risk → Optimization → Execution → Portfolio → Editorial
```

Las áreas exponen funciones puras, contratos Pydantic y un `SKILL.md`. El estado es
local y todo acceso a Polymarket está centralizado en `venue/` sobre el SDK oficial.

## Instalación completa

```bash
python3.11 -m venv .venv
.venv/bin/pip install --pre -e ".[dev,optimize,live,nfl]"
.venv/bin/pip check
cp .env.example .env
chmod 600 .env
```

Mantén `POLYMARKET_LIVE=0` y `POLYMARKET_KILL_SWITCH=1` durante instalación,
investigación, predicciones y backtests.

## Mercados soportados

| ID | Modelo principal | Estado operativo |
|---|---|---|
| `liga_mx_2026` | Elo + Bayes + TrueSkill; Poisson 1X2 | `draft`: observación y dry-run |
| `nfl_2026` | TrueSkill; Elo/Bayes auxiliares | `approved`: dry-run por defecto |

No se soporta ningún otro torneo. El registro canónico está en
`tournaments/registry.py`.

Liga MX no depende sólo de Poisson: el pipeline de fuerza calcula **Elo, Bayes y
TrueSkill**, y Poisson corre aparte para goles, 1X2 y doble oportunidad. La estrategia
actual elige el lado con un blend Elo+Bayes; cambiar esa combinación exige versionar la
estrategia y volver a probarla. NFL calcula las tres señales de fuerza, pero su estrategia
activa selecciona por TrueSkill.

## Datos y predicciones

```bash
# Liga MX
.venv/bin/python scripts/build_db.py --tournament liga_mx_2026 --sport football
.venv/bin/python data/liga_mx_2026/ingest/fetch_fixtures_pm.py --include-closed --apply
.venv/bin/python data/liga_mx_2026/ingest/load_history_fdcouk.py --apply
.venv/bin/python scripts/update_results.py --tournament liga_mx_2026 --apply

# NFL
.venv/bin/python scripts/migrate_nfl_data.py --since 2022

# Verificación y análisis read-only
.venv/bin/python scripts/check_freshness.py
.venv/bin/python scripts/scan_market.py --tournament liga_mx_2026 --hours 168 --observe-draft
.venv/bin/python scripts/scan_market.py --tournament nfl_2026 --hours 240
.venv/bin/python scripts/backtest_pipeline.py --tournament all --bankroll 1000
.venv/bin/python scripts/generate_reports.py
.venv/bin/python scripts/generate_reports.py --live \
  --publish-dir editorial/reports/_system/published
```

`generate_reports.py` toma hoy UTC como corte, detecta la próxima fecha de cada mercado
y actualiza dos HTML: predicciones conjuntas Liga MX/NFL y backtest conjunto hasta
hoy. También se ejecuta automáticamente al iniciar o reanudar una sesión de Codex. Las
rutas canónicas se documentan en `INIT.md`. Los últimos snapshots versionados llegan
con `git pull` bajo `editorial/reports/_system/published/`; GitHub Pages expone
[predicciones](https://hibra999.github.io/smart-polybets/) y
[backtest](https://hibra999.github.io/smart-polybets/backtest.html) con URLs estables.

## Ayuda para Codex

Escribe `Codex, help`. Codex abrirá `docs/PROMPTS.md` y mostrará las solicitudes
disponibles sin ejecutar ninguna. Las instrucciones completas están en `INIT.md`; los
gates de ejecución real, en `EXECUTION_GOLIVE.md`.

## Validación

```bash
.venv/bin/pytest
.venv/bin/ruff check .
git diff --check
```
