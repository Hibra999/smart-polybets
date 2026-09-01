# INIT — manual operativo de Codex

Este archivo es la fuente de arranque para operar PEPA. El repositorio admite sólo
Liga MX y NFL; la fecha, los fixtures, el saldo y la frescura siempre se consultan en
tiempo de ejecución.

## 1. Secuencia obligatoria al iniciar

1. Lee `AGENTS.md`, `README.md` y este archivo.
2. Abre todos los `docs/*.html` antes de cambiar el pipeline.
3. Lee el `SKILL.md` del área que vayas a usar.
4. Lee `tournaments/<id>/TOURNAMENT.md` y su `STRATEGY.md`.
5. Ejecuta `.venv/bin/python scripts/check_freshness.py` antes de predecir u operar.
6. Lee `EXECUTION_GOLIVE.md` antes de cualquier acción relacionada con dinero.

Ante un conflicto mandan, en este orden: seguridad, `AGENTS.md`, código y tests,
`tournaments/registry.py`, estrategia aplicable y documentación.

### Ayuda

Si el usuario escribe `Codex, help`, `help`, `ayuda`, “qué puedo pedir” o equivalente:

1. Invoca `$pepa-help` o abre `docs/PROMPTS.md`.
2. Muestra el catálogo agrupado por riesgo.
3. No ejecutes ningún prompt del catálogo.
4. Recuerda que Liga MX está en `draft` y que toda acción live necesita autorización
   específica; pedir ayuda nunca autoriza red, escritura ni dinero.

## 2. Instalación desde un clon limpio

Requiere Python 3.11. Los SQLite, `.env`, `.venv` y estados locales no se versionan.

```bash
python3.11 -m venv .venv
.venv/bin/pip install --pre -e ".[dev,optimize,live,nfl]"
.venv/bin/pip check
cp .env.example .env
chmod 600 .env
```

Estado seguro inicial:

```dotenv
POLYMARKET_LIVE=0
POLYMARKET_KILL_SWITCH=1
```

Nunca muestres ni copies al chat `.env`, private keys, API keys o respuestas de cuenta
crudas. `RELAYER_API_KEY` no sustituye `POLYMARKET_PRIVATE_KEY`; firmar una orden
requiere una clave EVM válida. La comprobación de cuenta es de sólo lectura:

```bash
.venv/bin/python scripts/polymarket_check.py
```

## 3. Reconstrucción de datos

### Liga MX Apertura 2026

```bash
.venv/bin/python scripts/build_db.py --tournament liga_mx_2026 --sport football
.venv/bin/python data/liga_mx_2026/ingest/fetch_fixtures_pm.py --include-closed --apply
.venv/bin/python data/liga_mx_2026/ingest/load_history_fdcouk.py --apply
.venv/bin/python scripts/update_results.py --tournament liga_mx_2026 --apply
```

La ingesta de Polymarket usa el tag `102448`; es incremental e idempotente. El Elo
aplica 80 puntos de localía y Poisson usa `neutral=False`.

### NFL 2026

```bash
.venv/bin/python scripts/migrate_nfl_data.py --since 2022
```

La migración descarga nflverse, crea el esquema y reemplaza el SQLite local con juegos
desde 2022 y calendario 2026. Después de cualquier ingesta:

```bash
.venv/bin/python scripts/check_freshness.py
```

No continúes si hay fixtures pasados todavía `scheduled`. `--force --reason` sólo se
usa tras autorización explícita y deja una justificación auditable.

## 4. Predicción, escaneo y backtest

Modelos disponibles:

- Liga MX: Elo, Bayes y TrueSkill forman el pipeline de fuerza; Poisson es un cuarto
  componente independiente para goles/1X2. La estrategia `draft` actual selecciona el
  lado con blend Elo+Bayes.
- NFL: Elo, Bayes y TrueSkill están disponibles; la estrategia aprobada selecciona por
  TrueSkill.

Todo este bloque es read-only o dry-run:

```bash
# Predicciones de la próxima fecha + backtest al día, sin indicar fechas manualmente
.venv/bin/python scripts/generate_reports.py

# Ambos torneos
.venv/bin/python scripts/backtest_pipeline.py --tournament all --bankroll 1000

# Liga MX: la estrategia es draft, por eso exige observe-draft
.venv/bin/python scripts/scan_market.py --tournament liga_mx_2026 \
  --hours 168 --observe-draft --json
.venv/bin/python scripts/poisson_predictions.py --tournament liga_mx_2026 \
  --date YYYY-MM-DD

# NFL
.venv/bin/python scripts/scan_market.py --tournament nfl_2026 --hours 240 --json
```

### Salida y reportes de backtest

`scripts/generate_reports.py` usa hoy UTC, elige la próxima fecha programada de cada
mercado y la última temporada con cuotas disponible. Genera exactamente dos paneles:

- `editorial/reports/_system/<hoy>_next-predictions.html`
- `editorial/reports/_system/<hoy>_backtest-to-date.html`

Para reproducir otro corte sin editar código:

```bash
.venv/bin/python scripts/generate_reports.py --as-of YYYY-MM-DD --bankroll 1000
```

Codex ejecuta el generador en `SessionStart` después del chequeo de frescura. Los HTML
son artefactos locales regenerables y no se versionan; el generador, las plantillas y las
reglas sí se versionan. `scripts/backtest_pipeline.py` conserva su salida de terminal y
acepta el mismo corte mediante `--as-of`.

Después de cada backtest, Codex debe informar: comando, torneo/temporada, bankroll,
fuente de precios, ROI, win rate, drawdown, cumplimiento de targets y ruta exacta del
reporte. Si no se generó HTML, debe decir claramente “sólo terminal; sin archivo”.

Obtén `YYYY-MM-DD` desde la base actual, no desde ejemplos históricos:

```bash
sqlite3 data/liga_mx_2026/liga_mx_2026.sqlite \
  "SELECT DISTINCT substr(kickoff_utc,1,10) FROM fixture WHERE status='scheduled' ORDER BY 1;"
sqlite3 data/nfl_2026/nfl_2026.sqlite \
  "SELECT DISTINCT substr(kickoff_utc,1,10) FROM fixture WHERE status='scheduled' ORDER BY 1;"
```

Simula el pipeline completo con estado separado:

```bash
.venv/bin/python scripts/place_bets.py --tournament liga_mx_2026 \
  --date YYYY-MM-DD --bankroll 1000 --observe-draft \
  --state /tmp/pepa-ligamx.json
.venv/bin/python scripts/place_bets.py --tournament nfl_2026 \
  --date YYYY-MM-DD --bankroll 1000 --state /tmp/pepa-nfl.json
```

`AUTO` es un veredicto, no prueba que se enviara dinero. En dry-run una decisión queda
`simulated`; sólo una respuesta del broker con `status=live` marca ejecución real.

## 5. Flujo de decisión

1. **Research:** carga estrategia, modelo, fixture y precio a través de `venue/`.
2. **Risk:** emite `AUTO`, `REVIEW`, `DISCARD` o `SKIP`.
3. **Optimization:** aplica Kelly fraccional y topes de exposición.
4. **Execution:** revalida precio, slippage, tick, tamaño y gates.
5. **Portfolio:** persiste idempotencia, decisión y resultado.
6. **Editorial:** resume después de decidir; publicar requiere otra autorización.

Liga MX permanece `draft`: `--observe-draft` sólo habilita observación en dry-run y es
incompatible con `--live`. NFL tiene estrategia `approved`, pero eso no autoriza live.
`REVIEW` nunca se ejecuta sin una aprobación humana independiente.

## 6. Ejecución real

No uses `--live` como parte de instalación, ingesta, análisis, predicción o backtest.
Una solicitud live debe nombrar la orden o acción concreta. Antes de ella:

1. Ejecuta freshness y la comprobación de cuenta.
2. Confirma estrategia aprobada y ausencia de `REVIEW`.
3. Verifica `POLYMARKET_LIVE=1`, signer válido y kill-switch en `0`.
4. Presenta precio, stake, slippage y pérdida máxima al usuario.
5. Exige la confirmación tipada que pide el CLI.

El procedimiento completo está en `EXECUTION_GOLIVE.md`. No publiques contenido ni
uses Metricool salvo petición explícita separada.

## 7. Validación antes de entregar

```bash
.venv/bin/pytest
.venv/bin/ruff check .
git diff --check
git status --short
```

Comprueba además que sólo `liga_mx_2026` y `nfl_2026` estén registrados y que no se
versionen `.env`, SQLite generados, estados temporales, credenciales ni respuestas de
cuenta. No cambies automáticamente el estado o los umbrales de una estrategia por el
resultado de un único backtest.

Tras validar un cambio solicitado, crea un commit descriptivo, sube la rama actual a
`origin` e informa su SHA. Nunca uses force-push ni reescribas historia sin autorización.
