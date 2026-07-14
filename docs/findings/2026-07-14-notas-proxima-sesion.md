# 2026-07-14 — Notas para la próxima sesión (handoff)

Sesión maratónica: carril CIO override, Liga MX completo (datos+modelos+backtests),
recorder/monitor/theta, EDA de goles. Este doc junta TODO lo abierto, en orden.

## 🔴 URGENTE / primero
1. **COMMIT PENDIENTE**: ~60 archivos sin versionar (override lane, Liga MX, theta,
   recorder, findings, reportes). El CIO no confirmó aún — preguntar y commitear
   (sugerido: commits separados por tema).
2. **✅ Spain RESUELTA: GANÓ 0-2 → +$28** (finalizada en DB, finding actualizado,
   dataset completo exportado y commiteado: 378 ticks + 1,539 lecturas finas).
   **Argentina Yes 22.22 × 0.315 sigue ABIERTA** (SF England-Argentina, 15-jul
   19:00 UTC): tras el partido `update_results.py --apply` + anotar en el finding
   sf-winner-bets. Si se quiere grabar el partido: recorder + export (runbook J1).
3. **Final + 3er puesto del WC NO existen en la DB** (el bracket terminaba en QF,
   las semis se insertaron a mano): cuando PM abra esos mercados, insertar
   `wc_151`/`wc_152` (mismo procedimiento, ver finding 2026-07-13-bracket).
   España ya está en la final (vs ganador de England-Argentina, 19-jul).
4. **ANÁLISIS DEL DATASET France-Spain** (mañana, acordado 2026-07-14): el export
   tiene el episodio completo del penal (min ~17: book 0.31→0.46 en segundos,
   depth 14,000→13.5 shares, Gamma rezagado) + el decay de France 0.36→0.15.
   Atacar la agenda de 8 puntos del finding theta-trade con estos datos.

## 🟠 Jueves 2026-07-16: Jornada 1 de Liga MX (runbook)
1. Diario: `fetch_fixtures_pm.py --apply` + `update_results.py --tournament liga_mx_2026 --apply`.
2. En jornada: `record_market_ticks.py` corriendo (terminal dedicada).
3. **Trade de prueba del theta** (sizing ≤$10, ver docs/theta-trade-manual.md):
   entrada NO del favorito vía `propose_bet.py --outcome no` + `orders.py`;
   salida con `theta_monitor.py` (comando `v` = hard stop). Objetivo: medir FEES
   y SLIPPAGE reales del round-trip (punto 7 de la agenda de análisis).
4. Post-jornada: `export_event_ticks.py --tournament liga_mx_2026 --all` + asentar
   trades con `backfill_manual_trades.py`.

## 🟡 Análisis pendientes (con los events/ capturados)
- Agenda completa de 8 puntos en `docs/findings/2026-07-14-theta-trade-lay-favorito.md`
  (latencia de repricing, evaporación de depth, spread(t), decay real, lag Gamma/CLOB,
  hedge con draw, fees reales, asimetría 1T/2T).
- Cruzar el hazard de goles (EDA `2026-07-14-ligamx-goles-eda.md` + reporte
  `docs/ligamx-goles-eda.html`) con los price paths → curva EV(salida en min m)
  → decidir `from_min`/`hard_exit_min`/`tp_pct` del theta_lay_v1 con datos.
  Hipótesis: hard_exit 60-75 (no 105), from_min 20-25, regla de rojas.

## 🟢 Mejoras identificadas, no urgentes
- **Maker-first en orders.py**: los mercados sports pagan rebate al maker y cobran
  ~5% taker; postear dentro del spread en vez de cruzar (finding sesgos-mercado).
- **Regla favorito-a-mejor-precio**: solo tomar favoritos cuando PM > Max de casas;
  nunca comprar longshots/empates a precio retail (finding sesgos-mercado).
- **Logística multinomial como yardstick** (le gana al Poisson ~1% log-loss;
  scripts/ligamx_ml_experiment.py) — promover a adapters/ si se quiere usar.
- **Opción C del diseño de trazabilidad**: match_winner_v2 con side_criterion
  poisson (apuntar a NFL 2026 — arranca 2026-09-06).
- REVIEWs viejas del 20-jun en el ledger sin expirar (marcar `expired`).
- Tracker PM vs Poisson vs cierre para `match_winner_ligamx_v1` (sigue draft:
  el backtest dio SIN edge vs cierre; solo aprobar con evidencia de PM blando).
- `theta-trade-manual.html` es copia manual del .md — considerar generarlo.

## Gotchas nuevos de hoy (ya en CLAUDE.md, refrescar memoria)
- In-play: **solo el book del CLOB** (Gamma y el score feed van segundos atrás —
  visto en vivo con el penal de España: book 0.4625 vs Gamma 0.3125).
- La profundidad se evapora en eventos (14,000 → 13.5 shares durante el penal).
- ESPN llama "Santos" a Santos Laguna (mapeo en fetch_goal_minutes_espn.py).
- El buffer de ticks es rodante y gitignored; los `events/` exportados SÍ se
  versionan (data por torneo y evento).
