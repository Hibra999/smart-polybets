# CLAUDE.md — Sports Quant Trading System (contexto global del repo)

Hedge fund sintético de un operador para mercados de predicción deportivos en
Polymarket. Claude actúa como analista cuantitativo, gestor de riesgo y operador;
el humano es el CIO que aprueba lo ambiguo y delega lo obvio.

## Protocolo de sesión (leer PRIMERO)
Las sesiones suelen arrancar fuera de este directorio → este archivo **no se auto-carga**.
Antes de cualquier tarea en este repo, todo agente debe:
1. **Leer este `CLAUDE.md` completo** (contiene los gotchas verificados que evitan
   redescubrir por código lo ya aprendido).
2. **Revisar los findings recientes**: `ls docs/findings/` (llevan fecha; leer los que
   toquen el área de la tarea). Si se va a operar en vivo → `EXECUTION_GOLIVE.md`.
3. **Leer el `SKILL.md`/`STRATEGY.md` del área a tocar** (cada carpeta tiene el suyo).
4. **Status rápido del repo y la cuenta**:
   ```bash
   git log --oneline -5 && git status -s      # dónde quedó la última sesión
   python scripts/account.py                  # cuenta live (cash, posiciones, W-L)
   python scripts/scan_market.py --hours 48   # oportunidades próximas (dry-run; WC)
   ```
5. **Antes de CUALQUIER sugerencia o apuesta: refrescar datos** (los modelos reproducen
   los fixtures jugados en runtime → DB desactualizada = edges falsos). POR TORNEO:
   ```bash
   # FIFA World Cup 2026 (hasta 2026-07-19; semis jugadas, quedan 3er puesto/final):
   python scripts/update_results.py --apply            # finaliza jugados (Exact Score/escalera)
   python scripts/sync_upcoming_fixtures.py --apply    # placeholders -> equipos reales
   #   ⚠️ el bracket de la DB terminaba en QF: final y 3er puesto se insertan A MANO
   #   cuando PM los abra (ver gotcha del bracket + finding 2026-07-13).
   # Liga MX Apertura 2026 (arrancó 2026-07-16):
   python data/liga_mx_2026/ingest/fetch_fixtures_pm.py --apply       # jornadas nuevas
   python scripts/update_results.py --tournament liga_mx_2026 --apply # finaliza jugados
   #   en DÍAS DE JORNADA además: python scripts/record_market_ticks.py  (recorder 1/min)
   ```
   **Enforced (2026-07-17):** el hook `SessionStart` corre `scripts/check_freshness.py`
   al arrancar y avisa si hay datos viejos; las acciones de dinero (`propose_bet`,
   `place_bets`, `orders`) **se bloquean** ante `fixtures_finalized` incumplido salvo
   `--force --reason`. Diseño: `docs/superpowers/specs/2026-07-17-mandatory-dependency-hooks-design.md`;
   referencia: `docs/dependency-hooks.html`.
   Verificar que quede limpio: 0 fixtures con kickoff pasado en status `scheduled`
   (salvo partidos EN JUEGO ahora). El 2026-07-09 se apostó con los 8 octavos sin
   ingestar — ver `docs/findings/2026-07-09-data-freshness-gaps.md`.
Regla práctica: si una pregunta operativa parece requerir leer código de `venue/`,
`execution/` o `scripts/`, primero buscar la respuesta aquí y en `docs/findings/` —
lo más probable es que ya esté documentada.

## Principio rector
**Reproducibilidad hacia adelante**: cada decisión es el resultado determinístico
de inputs documentados procesados por funciones versionadas con contratos
explícitos (schemas Pydantic). Mismos inputs → misma decisión.

## Mapa del repo
| Carpeta | Rol |
|---|---|
| `core/` | utilidades compartidas, sin lógica de negocio (tipos, excepciones, strategy parser, `local_state`, `polymarket_client`, `timez`, `preconditions`) |
| `data/` | un SQLite por torneo + DDL canónico por deporte (`_schema/`) |
| `adapters/` | única capa que lee los SQLite (read-only) + adapters de modelo (Elo, Bayes, TrueSkill, Poisson) |
| `venue/` | **única interfaz con Polymarket**: `gateway` (saldos/posiciones/órdenes/best_ask sobre el SDK), `discovery` (eventos vía SDK), `books` (order books + price history públicos), `ticks` (extracción pura de snapshots), `matching` (mapeo mercado↔partido), `results` (marcadores desde mercados resueltos). **Ningún script llama al SDK/cliente directo** — siempre a través de venue/. |
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

## Gotchas de ejecución en vivo (place_bets / orders) — FIXED 2026-07-14
Los dos bugs verificados el 2026-07-09 quedaron corregidos:
1. `place_bets.py` ya llama `load_env()` (antes, con `--live` sin key en el entorno,
   degradaba **silenciosamente a dry-run** y no colocaba nada).
2. Un dry-run ya **NO** marca `status=executed`: queda **`simulated`** (nuevo status,
   `LocalStateClient.mark_simulated`), que **no bloquea la idempotencia** — el run live
   siguiente reprocesa la decisión. Sólo un fill `live` marca `executed` (paridad con
   `orders.py`). Tests: `test_full_analysis_auto`.
Ruta confiable para colocar en vivo: **`orders.py --approve <key> --live --confirm <monto>`**
(carga env, gate `POLYMARKET_LIVE=1` + key + kill-switch, y confirmación tipeada del USDC).

## Apuestas manuales (CIO override) — SIEMPRE por el pipeline
Toda apuesta que la estrategia activa no genera (lado Poisson en mercados a 90', totales
O/U, sizing decidido por el CIO) va por el **carril override** — NO por broker directo:
```bash
# 1. proponer: riesgo real (edge/volumen/drawdown/horas/exposure) puede DISCARDear;
#    si pasa, queda como Decision REVIEW en el ledger (strategy_id=cio_override)
python scripts/propose_bet.py --market "Will Spain win on 2026-07-14?" \
    --stake 12 --model-prob 0.379 --reason "Poisson corregido vs ask"  # [--outcome no] [--dry-run]
# 2. colocar: gates live + confirmación tipeada; mark_executed sólo si el fill es live
python scripts/orders.py --approve <key> --live --confirm 12.00
```
Un override **nunca es AUTO** (REVIEW forzado) y `--reason` es obligatoria (queda en el
ledger). Key idempotente estándar → no se puede proponer dos veces el mismo día. El broker
directo (`place_totals_qf.py`/`place_winner_sf.py`) queda como escape hatch de emergencia;
si se usa, asentar después con `scripts/backfill_manual_trades.py` (idempotente — ya
retro-registró las 7 operaciones pre-carril del 2026-07-05..13).
Diseño: `docs/superpowers/specs/2026-07-14-cio-override-lane-design.md`.

## Apostar markets de goles / totales (O/U, BTTS, spread): NO hay ruta de estrategia
La estrategia activa (`match_winner_wc_v1`) **solo apuesta el ganador** (win/double_chance).
Los markets O/U, BTTS y spread (evento "`{H} vs. {A} - More Markets`") el sistema los usa
**solo para reconstruir marcadores** (`update_results.py`), **no para apostar**. El pipeline
(`place_bets.py`/`orders.py`) no puede colocar una apuesta de totales.

Para apostar un total hoy → **carril CIO override** (`propose_bet.py`, ver sección de
apuestas manuales): el outcome `yes` es Over y `no` es Under en los mercados O/U. La orden
manual de bajo nivel con `execution.functions.broker.PolymarketBroker` (TradeOrder directo
al token) queda solo como escape hatch. Gotchas del path de bajo nivel:
- **`gateway.best_ask(token)` devuelve None sin `private_key`.** Construir el gateway con la
  key (`PolymarketGateway(live=True, private_key=..., funder=...)`) para leer el ask real.
- `broker.place()` manda un **LIMIT** (`place_limit_order`) y redondea el precio al tick.
- Gate live: `--live` **y** `POLYMARKET_LIVE=1` **y** key **y** kill-switch off. `load_env`
  usa `setdefault` → un `export POLYMARKET_LIVE=1` inline gana sin tocar `.env`.
- ⚠️ **Bypassa el motor de riesgo, la idempotencia y el `LocalState`**: la apuesta NO queda
  registrada en el ledger local (consistente con que el PnL se lee de la cuenta LIVE, ver
  sección de PnL). Anotar la operación a mano si se necesita traza en el repo.
- ⚠️ **Tick 0.0025 requiere `polymarket-client >= 0.1.0b12`** — VERIFICADO 2026-07-09. Los
  mercados de totales del WC usan tick `0.0025`; con el SDK `0.1.0b11` **todos** los paths de
  orden (limit Y market, incluso `estimate_market_price`) fallan con `UnexpectedResponseError:
  Unsupported tick size received: 0.0025` (el mapa `_ROUNDING_BY_TICK` interno no lo incluye).
  Las apuestas de ganador no lo sufren (tick 0.01). Fix: `pip install --pre -U polymarket-client`
  (b12+ añade 0.005 y 0.0025, ver changelog). Tras actualizar, revalidar `scripts/account.py`.
  Script de referencia usado: `scripts/place_totals_qf.py`; detalle y traza de la operación en
  `docs/findings/2026-07-09-totals-live-sdk-tick.md`.

## Mercados knockout "Will X win": resuelven a 90 minutos → usar Poisson, NO el blend
VERIFICADO 2026-07-09 en la descripción del mercado (France vs Morocco, QF): *"This market
refers only to the outcome within the first 90 minutes of regular play plus stoppage time."*
Un empate al 90' resuelve **No** aunque el equipo avance por penales (el mercado de draw
resuelve Yes). Implicaciones:
- El **blend Elo/Bayes/TrueSkill NO modela el empate** → sobreestima sistemáticamente
  P(gana) en knockout y puede inflar edges fantasma (ej. 2026-07-09: blend France 71.5% vs
  mercado 61%; el Poisson 1X2 daba 56% → la apuesta estaba CARA, no barata).
- Para mercados a 90' (win, draw, totales, BTTS), el yardstick correcto es el **Poisson 1X2 /
  goles** (`wc_poisson_suggestions.py`), que sí descuenta el empate.
- El blend sigue siendo válido para mercados de **avance/progresión** (si existieran) o como
  señal de fuerza relativa — no para precio de "win a 90'" en eliminatorias.

## Sincronizar eliminatorias (placeholders de bracket → equipos reales)
La DB modela el knockout con **placeholders de bracket** (`group_c_winner`,
`round_of_32_4_winner`, `round_of_16_1_winner`, …). Gotcha: esos placeholders **existen
como filas en la tabla `team`** (56 filas), así que "¿es real?" NO se decide por
pertenencia a `team`. **Un equipo real tiene `elo_rating` no-NULL; un placeholder lo tiene
NULL** — ese es el discriminador robusto (los 48 equipos vs 56 placeholders).
```bash
python scripts/sync_upcoming_fixtures.py            # dry-run
python scripts/sync_upcoming_fixtures.py --apply    # backup .sqlite + reescribe
```
Trae los partidos abiertos de Polymarket (SDK, `venue.discovery`) y reescribe
`home_team_id`/`away_team_id`/`kickoff_utc` de los placeholders pendientes, mapeando 1:1
por orden de kickoff. **Es idempotente**: descarta los partidos de PM que ya existen como
fixture con equipos reales, así un re-run NO duplica en los slots sobrantes. Después,
`scripts/update_results.py --apply` finaliza los ya jugados (marcador desde los mercados
More Markets de PM). Ver [[project-wc2026-knockout-phase]].

⚠️ **Gotcha (VERIFICADO 2026-07-13): el bracket de la DB termina en CUARTOS.** La DB tiene
100 fixtures y el torneo 104: no hay placeholders para semis/3er puesto/final, así que el sync
reporta "N partidos PM vs 0 placeholders" y no escribe nada. Fix: insertar el fixture a mano
(backup → INSERT copiando convenciones de los QF: `phase_id='group_stage'`, `neutral_venue=1`,
id consecutivo). Hecho para las semis (`wc_149`/`wc_150`); **falta repetirlo para 3er puesto y
final** cuando PM los abra. Ver `docs/findings/2026-07-13-bracket-sin-semifinales.md`.

⚠️ **Gotcha (VERIFICADO 2026-07-09): el sync solo ve mercados ABIERTOS.** Si un partido de
knockout se juega (su mercado cierra) entre dos corridas del sync, su placeholder queda
huérfano para siempre: `update_results` tampoco lo encuentra (matchea por nombres de equipos
y el placeholder no tiene). Así se perdieron `wc_121` (South Africa–Canada, R32) y `wc_144`
(Canada–Morocco, R16). Detección: fixtures con kickoff pasado en `scheduled` cuyo home/away
sea placeholder. Recuperación: identificar el partido real en `match_events(closed=True)`
(par de equipos sin fixture en DB), escribir equipos+kickoff a mano (con backup del .sqlite)
y re-correr `update_results.py --apply`. Prevención: correr el sync a diario durante rondas
de eliminación. Detalle: `docs/findings/2026-07-09-data-freshness-gaps.md`.

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

⚠️ **PnL neto = FLUJO DE CAJA, no snapshot (VERIFICADO 2026-07-17).** El método correcto —el
único que cuadra con la UI de Polymarket— es `PnL = Σ ventas + Σ redenciones − Σ compras`.
`scripts/account.py` ya lo muestra en la línea `RESUELTAS (N: W-L) · PnL neto` (y en el campo
`realized_pnl` del `--json`), con una línea de **reconciliación** debajo. **Usar ese número tal
cual** — no restar nada a mano. Dos trampas que llevaron a reportes malos, ambas resueltas:
1. El array `closed` del `--json` **NO** es el PnL completo: las apuestas resueltas y PERDIDAS no
   se mueven a `closed`, quedan como **posiciones abiertas con `current_price=0`**
   (`redeemable=True`, `percent_pnl≈-100%`, `cash_pnl=-invertido`; Polymarket no las auto-limpia).
   Sumar solo `closed` **subestima pérdidas** (el 2026-07-17 reporté +$337.83 leyendo solo `closed`).
2. El método de **snapshot** (fusionar `closed` + esos perdedores a $0 como −invertido) **sobreestima
   pérdidas** cuando hubo **cierres anticipados**: vender una posición perdedora antes de la
   resolución recupera salvamento que el snapshot no ve. El 2026-07-17 daba **−$27.40** por snapshot
   cuando el neto real (flujo de caja) era **−$19.58**. Ver `docs/findings/2026-07-17-pnl-cashflow-vs-snapshot.md`.
Ojo con las columnas per-fila: `GANÓ/PERDIÓ` etiqueta **redimido vs sin-redimir** (no el resultado
real) y las filas `PERDIÓ` asumen pérdida total; el que vale es el **PnL neto** de la cabecera.

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
- **Liga MX Apertura 2026** (2026-07-16 → 2026-12-13): registrado en `tournaments/registry.py`
  con estrategia en **draft (NO opera)**. Equipos (18, incluye **Atlante**, no Mazatlán) y
  calendario se ingieren de Polymarket (tag **102448**, ventana rodante ~2 jornadas →
  **correr a diario** `data/liga_mx_2026/ingest/fetch_fixtures_pm.py --apply` +
  `scripts/update_results.py --tournament liga_mx_2026 --apply`). **Localía cableada**
  (2026-07-14): `TournamentConfig.{home_adv_elo=65, neutral_venue=False}` → Elo con
  `home_adv` y Poisson `neutral=False`. **Historia y calibración cargadas (2026-07-14)**:
  football-data MEX.csv → `historical_match` (336 partidos 2025/26, Poisson home_factor
  1.40) + seeds Elo reales (Cruz Azul 1695…Puebla 1310; Atlante=1500 sin historia) +
  `home_adv_elo=80` calibrado. ⚠️ **Backtest 2025/26: SIN edge vs cuotas de cierre**
  (ROI negativo) → estrategia sigue draft; plan = observar J1-J3 si Polymarket precia
  peor que el cierre (finding `2026-07-14-ligamx-backtest.md`). **Minutos de gol + rojas**
  (fuente ESPN, tabla `match_timeline_event`): EDA en finding `2026-07-14-ligamx-goles-eda.md`
  + reporte `editorial/reports/liga_mx_2026/ligamx-goles-eda.html` — Liga MX es más hostil que el WC para el theta
  (favorito ya anotó al min 30 en 37%; bin 76-90 el más denso; rojas en 34% de partidos).
  Ver `tournaments/liga_mx_2026/TOURNAMENT.md` y `data/liga_mx_2026/DATA_SOURCES.md`.
- **NFL 2026**: registrado en `tournaments/registry.py`, ventana 2026-09-06 → 2027-02-08.
  Modelo **TrueSkill evolutivo** (`AmericanFootballTrueSkillAdapter`, migrado de `sports_bet`;
  Elo/Bayes disponibles como ensemble en `adapters/american_football/nfl_ensemble.py`).
  Estrategia **`game_winner_v1` (status: approved)**. `polymarket_tag_id` aún sin setear en
  el registry. Datos vía `scripts/migrate_nfl_data.py` + `data/nfl_2026/ingest/`; reportes
  `scripts/nfl_*_report.py`. Ver `tournaments/nfl_2026/TOURNAMENT.md`.
- **`update_results.py` es multi-torneo** (2026-07-14): `--tournament <id>` usa el
  `polymarket_tag_id` del registry; marcador vía mercado **Exact Score** (Liga MX) con
  fallback a la escalera O/U (Mundial). Lógica pura en `venue/results.py`.
- **Recorder de ticks** (2026-07-14): `scripts/record_market_ticks.py` guarda 1
  snapshot/min de los mercados winner/draw abiertos (bid/ask/spread/vol + score live +
  book depth en ventana kickoff±) en `data/<tid>/market_ticks.sqlite` (gitignored,
  buffer rodante). **Post-evento**: `scripts/export_event_ticks.py` exporta cada
  partido a su carpeta versionable `data/<tid>/events/<fecha>-<evento>/ticks.sqlite`
  (ticks + capturas finas del monitor + sesiones + meta; idempotente) — la data de
  mercado queda POR TORNEO Y POR EVENTO para análisis posterior.
  **Correr en días de jornada de Liga MX** — es el insumo para validar el theta trade
  (lay del favorito con salida anticipada, finding `2026-07-14-theta-trade-lay-favorito.md`:
  +7 a +21% bruto en los 26 KO del WC con price history de PM; pendiente validar
  ejecutabilidad con spread/depth reales de Liga MX).
- **Theta monitor (CLI)** (2026-07-14): `scripts/theta_monitor.py` cierra el ciclo del
  theta trade — lee el book cada 5s (~460ms/lectura), imprime lecturas+PnL, y vende
  AUTOMÁTICO al disparo de la regla pura de `execution/functions/theta_exit.py` (TP
  configurable desde min X + salida dura min Y + stop opcional). **Comandos en vivo**:
  `v`+Enter = HARD STOP manual (vende YA, con 3 reintentos a bid fresco), `p` = PnL,
  `q`/Ctrl+C = salir sin vender. **Persiste TODO** (cada lectura, PnL, intentos de venta,
  errores) en `theta_session`/`theta_tick` de `market_ticks.sqlite` — si la venta falla,
  imprime el resumen, deja instrucciones y los datos quedan. Dry-run default; live =
  gates + confirmación tipeada al inicio. La venta bypassea el ledger → asentar con
  `backfill_manual_trades.py`. **Estrategia formal**: `tournaments/liga_mx_2026/strategies/
  theta_lay_v1/STRATEGY.md` (draft) · **manual de operación con todos los parámetros y
  cómo obtener el id de mercado (`--list`)**: `docs/theta-trade-manual.md`. Flexible a
  cualquier torneo registrado (`--tournament`) o cualquier mercado de PM (`--token`).

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
