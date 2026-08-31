# Inicio de sesión para agentes LLM

Este archivo es el handoff operativo del repositorio. La instantánea puede quedar
obsoleta; los comandos y el estado actual del código o de los datos siempre mandan.

## 1. Leer antes de actuar

1. `AGENTS.md` para reglas del repositorio y seguridad.
2. `README.md` para arquitectura y flujo unidireccional.
3. El `SKILL.md` del área que se vaya a tocar.
4. `tournaments/<tournament_id>/TOURNAMENT.md` y la estrategia activa en
   `tournaments/<tournament_id>/strategies/*/STRATEGY.md`.
5. `EXECUTION_GOLIVE.md` antes de cualquier trabajo relacionado con dinero real.

No llamar al SDK de Polymarket desde scripts o paquetes de dominio: todo acceso pasa
por `venue/`. No cambiar estados ni umbrales de estrategias sólo porque un backtest
salga bien o mal.

## 2. Arranque desde un clon limpio

Requiere Python 3.11. Los SQLite, `.env`, `.venv`, estados y respuestas generadas no
se versionan.

```bash
python3.11 -m venv .venv
.venv/bin/pip install --pre -e ".[dev,optimize,live,nfl]"
.venv/bin/pip check
cp .env.example .env
chmod 600 .env
```

Mantener inicialmente:

```dotenv
POLYMARKET_LIVE=0
POLYMARKET_KILL_SWITCH=1
```

`RELAYER_API_KEY` y `RELAYER_API_KEY_ADDRESS` habilitan autenticación gasless del
relayer, pero no sustituyen `POLYMARKET_PRIVATE_KEY`: consultar la cuenta y firmar
órdenes requiere una private key EVM válida. Nunca imprimir, copiar al chat ni
versionar `.env`, private keys, API keys o respuestas autenticadas crudas. El checker
seguro sólo muestra direcciones públicas, balance y allowance.

La comprobación de cuenta es de sólo lectura y carga `.env` automáticamente:

```bash
.venv/bin/python scripts/polymarket_check.py
```

Si sólo hay credenciales del relayer, es correcto que informe que el relayer está
configurado y termine con un error sanitizado por falta de signer. En ese estado no
están verificados signer, wallet derivada, balance ni allowance.

## 3. Reconstruir datos locales

### Liga MX Apertura 2026

```bash
.venv/bin/python scripts/build_db.py --tournament liga_mx_2026 --sport football
.venv/bin/python data/liga_mx_2026/ingest/fetch_fixtures_pm.py --include-closed --apply
.venv/bin/python data/liga_mx_2026/ingest/load_history_fdcouk.py --apply
.venv/bin/python scripts/update_results.py --tournament liga_mx_2026 --apply
```

La ingesta mezcla mercados abiertos/cerrados, limita al Apertura 2026 y deduplica por
local, visitante y fecha. Ejecutar `fetch_fixtures_pm.py` y `update_results.py` a diario
durante el torneo para no perder mercados de la ventana rodante.

### NFL 2026

`migrate_nfl_data.py` descarga nflverse, crea el schema y reemplaza su SQLite destino;
no hace falta ejecutar `build_db.py` antes.

```bash
.venv/bin/python scripts/migrate_nfl_data.py --since 2022
```

### Mundial 2026 archivado

El soporte sigue registrado, pero el clon no incluye su SQLite ni el `worldcup.db`
externo. Sólo reconstruirlo cuando exista esa fuente:

```bash
.venv/bin/python scripts/migrate_worldcup_data.py --source /ruta/absoluta/worldcup.db
```

Después de cualquier ingesta:

```bash
.venv/bin/python scripts/check_freshness.py
```

No continuar con el pipeline si hay partidos pasados todavía `scheduled`. No usar
`--force` salvo autorización explícita del usuario y una razón auditable.

## 4. Operación segura y backtesting

Backtest multitorneo con bankroll teórico de USD 1,000:

```bash
.venv/bin/python scripts/backtest_pipeline.py --tournament all --bankroll 1000
# Para tooling, añadir --json; incluye el detalle completo de apuestas.
```

Buscar oportunidades próximas, siempre read-only:

```bash
.venv/bin/python scripts/scan_market.py --tournament liga_mx_2026 \
  --sport football --hours 168 --observe-draft --json
.venv/bin/python scripts/scan_market.py --tournament nfl_2026 \
  --sport american_football --hours 168 --json
```

Obtener las fechas desde los fixtures actuales; no reutilizar fechas de esta
instantánea:

```bash
sqlite3 data/liga_mx_2026/liga_mx_2026.sqlite \
  "SELECT DISTINCT substr(kickoff_utc,1,10) FROM fixture WHERE status='scheduled' ORDER BY 1;"
sqlite3 data/nfl_2026/nfl_2026.sqlite \
  "SELECT DISTINCT substr(kickoff_utc,1,10) FROM fixture WHERE status='scheduled' ORDER BY 1;"
```

Para cada fecha elegida, ejecutar el pipeline sin `--live` y con estado temporal
separado:

```bash
.venv/bin/python scripts/place_bets.py --tournament liga_mx_2026 \
  --date YYYY-MM-DD --bankroll 1000 --observe-draft \
  --state /tmp/pypro_liga_mx_state.json
.venv/bin/python scripts/place_bets.py --tournament nfl_2026 \
  --date YYYY-MM-DD --bankroll 1000 \
  --state /tmp/pypro_nfl_state.json
```

`--observe-draft` autoriza únicamente observar una estrategia draft en dry-run y se
rechaza junto con `--live`. `AUTO`, `REVIEW`, `DISCARD`, `SKIP`, volumen insuficiente o
ausencia de mercado son resultados legítimos. Nunca transformar uno en una orden real.

Revisar el estado simulado con:

```bash
.venv/bin/python scripts/portfolio.py --state /tmp/pypro_liga_mx_state.json \
  --bankroll 1000 --tournament liga_mx_2026
```

Limitaciones actuales: `editorial_daily.py` sigue cableado al Mundial y el settlement
de `portfolio.py` sólo tiene reader de football; no presentarlos como soporte genérico
de Liga MX/NFL sin implementar y probar primero esa generalización. Metricool queda
fuera del pipeline de trading y nunca debe publicarse con `--publish` por accidente.

## 5. Instantánea verificada: 2026-08-31 UTC

La funcionalidad de observación multitorneo, relayer y backtesting llegó hasta el
commit base `f04bfdc`. Al iniciar una sesión nueva, ejecutar `git status` y `git log`
porque el commit de documentación posterior será más reciente.

- Liga MX local: 68 fixtures, 54 `finished` y 14 `scheduled`; los siguientes empiezan
  el 2026-09-05. Freshness estaba OK.
- Backtest Liga MX: cobertura 336/336; AUTO 171, REVIEW 125, DISCARD 22, SKIP 18;
  81W-90L, ROI -14.3%, yield -3.4%, max drawdown 28.2%, bankroll final USD 856.75.
  Falló los tres targets y `match_winner_ligamx_v1` continúa `draft`.
- NFL local: 1,139 fixtures `finished` y 272 `scheduled`; primeros juegos 2026-09-09
  Patriots-Seahawks y 2026-09-10 49ers-Rams.
- Backtest NFL: cobertura 272/272; AUTO 95, REVIEW 37, DISCARD 140; 43W-52L,
  ROI -62.7%, yield -13.3%, max drawdown 70.6%, bankroll final USD 373.17. Falló
  los tres targets; la estrategia versionada sigue `approved` y no debe alterarse
  automáticamente.
- Mundial: backtest no disponible porque falta
  `data/fifa_world_cup_2026/fifa_world_cup_2026.sqlite`.
- Última observación: Liga MX produjo nueve `SKIP` por volumen menor a USD 500; NFL
  produjo un `SKIP` por falta de mercado elegible. No se creó estado persistente,
  ninguna respuesta tuvo `status=live` y no se envió ninguna orden real.
- La configuración local detectaba relayer, pero no un signer EVM válido; por ello no
  se confirmó cuenta, balance ni allowance. El valor real de las credenciales nunca
  pertenece a Git.

## 6. Validación y entrega

```bash
.venv/bin/pytest
.venv/bin/ruff check .
git diff --check
git status --short
```

La suite tenía 261 pruebas pasando. Ruff global tenía 394 hallazgos heredados; no hacer
un barrido masivo ajeno a la tarea. Exigir Ruff limpio en los Python modificados y
registrar con precisión cualquier baseline que siga existiendo.

Antes de commit/push, revisar que no estén staged `.env`, SQLite, estado temporal,
JSON autenticado ni secretos. Usar Conventional Commits y no habilitar live como parte
de una tarea de documentación, análisis, ingesta o backtest.
