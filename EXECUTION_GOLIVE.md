# Ejecución automática de apuestas — guía de go-live

El sistema coloca apuestas automáticamente en Polymarket. **Por defecto corre en
dry-run** (no toca la wallet). Esta guía cubre el flujo y los pasos para ir a vivo.

## Flujo

```
scan fixtures del día
  → research (modelo Elo+Bayes+TrueSkill)
  → cuotas LIVE de Polymarket (PolymarketLiveSource, Gamma API)
  → risk.evaluate → AUTO / REVIEW / DISCARD
  → optimization.size_single (Kelly fraccional)
  → execution: orden al best_ask live + guarda de slippage
  → PolymarketBroker.place  (dry-run | live)
  → estado local (idempotencia, no doble-apostar)
```

Sólo los **AUTO** se colocan. REVIEW espera aprobación humana; DISCARD/SKIP no operan.

## Correr (dry-run, sin riesgo)

```bash
python scripts/scan_market.py --hours 72                  # edge modelo-Polymarket, próximas 72h (sports-as-plugins seam)
python scripts/scan_market.py --json                      # misma salida en JSON
python scripts/place_bets.py --date 2026-06-20            # qué se colocaría hoy
python scripts/wc_suggestions.py --date 2026-06-20        # tabla de sugerencias
python scripts/portfolio.py                               # portafolio + trades (abiertos/cerrados/pendientes)
python scripts/account.py                                # saldo, posiciones y órdenes live (requiere .[live]+key)
python scripts/account.py --reconcile                    # drift vs estado local + ajusta bankroll
python scripts/orders.py --list                          # REVIEWs pendientes + órdenes abiertas live
python scripts/orders.py --approve <key> [--live]        # coloca la orden de una REVIEW (repricing + confirmación)
python scripts/orders.py --cancel <order_id> [--live]    # cancela una orden abierta
```

### Carril CIO override (apuestas manuales, 2026-07-14)
Toda apuesta que la estrategia activa no genera va por acá — NUNCA por broker directo:
```bash
python scripts/propose_bet.py --market "Will X win…" --stake 12 \
    --model-prob 0.55 --reason "…" [--outcome no] [--dry-run]   # Decision REVIEW en el ledger
python scripts/orders.py --approve <key> --live --confirm 12.00 # colocación con gates
python scripts/backfill_manual_trades.py --apply                # asentar trades hechos por fuera
```

### Trading intra-partido (theta trade, 2026-07-14 — draft, ver docs/theta-trade-manual.md)
```bash
python scripts/record_market_ticks.py                    # recorder 1/min (correr en jornadas)
python scripts/theta_monitor.py --list [filtro]          # descubrir mercados/tokens
python scripts/theta_monitor.py --market "…" --entry P --shares N [--live]
#   comandos en vivo: v = HARD STOP (vende YA) · p = PnL · q = salir sin vender
```

`portfolio.py` lee el estado local (`data/agent_state.json`) y asienta el PnL de los
trades cerrados contra los resultados de los fixtures. Estados: ABIERTA (ejecutada,
partido sin terminar), CERRADA (ejecutada, terminada → PnL WON/LOST), PENDIENTE
(recomendada, esperando aprobación del CIO). Acepta `--bankroll`, `--tournament` y `--json`.

En dry-run, cada AUTO imprime la orden EXACTA que se enviaría (token_id real,
precio redondeado al tick, shares, neg_risk).

## Ir a LIVE (dinero real)

1. **Instalar el extra live** (ya instalado en este entorno):
   ```bash
   pip install --pre -e ".[live]"     # polymarket-client (SDK oficial V2)
   ```
2. **Fondos**: depositar el colateral **pUSD** en la wallet de Polymarket. El SDK V2
   **deriva solo** el proxy wallet y los contratos pUSD, así que no hace falta el flujo
   manual de allowances Exchange/CTF de la V1 (la aprobación inicial se hace una vez
   desde la UI de Polymarket).
3. **Credenciales** en `.env` (ver `.env.example`):
   - `POLYMARKET_PRIVATE_KEY` — llave que firma (¡secreta!).
   - `POLYMARKET_FUNDER` — **opcional** (override). El SDK V2 deriva el proxy wallet de
     la private key; `signature_type` ya **no** se configura (unificado en el SDK).
   - `RELAYER_API_KEY` + `RELAYER_API_KEY_ADDRESS` — **opcionales**, habilitan
     workflows gasless. No reemplazan la firma de `POLYMARKET_PRIVATE_KEY`.
   - `POLYMARKET_LIVE=1` — interruptor maestro.
4. **Ejecutar**:
   ```bash
   python scripts/place_bets.py --date 2026-06-20 --live
   ```

El broker sólo envía si: `--live` **y** `POLYMARKET_LIVE=1` **y** hay private key
**y** el kill-switch está apagado. Si falta cualquiera, sigue en dry-run.

## Backtest del pipeline

El runner multitorneo reutiliza la estrategia activa, selección de lado, Risk y
Kelly. Los precios son proxies históricos de cierre; el volumen se asume en el
mínimo de la estrategia porque las fuentes históricas no lo conservan.

```bash
python scripts/backtest_pipeline.py --tournament liga_mx_2026 --bankroll 1000
python scripts/backtest_pipeline.py --tournament nfl_2026 --season 2025 --json
python scripts/backtest_pipeline.py --tournament all
```

## Guardas de seguridad (defensa en profundidad)

| Guarda | Qué hace |
|---|---|
| Dry-run por defecto | Nada se envía sin opt-in explícito (flag + env + creds). |
| `POLYMARKET_KILL_SWITCH=1` | Bloquea toda ejecución real al instante. |
| Idempotencia | Estado local (`data/agent_state.json`): no re-apuesta una key ya colocada. |
| Anti-REVIEW | `execution_tools.submit` levanta si la decisión requiere aprobación. |
| Slippage | No ejecuta si el best_ask se movió > tolerancia (15%) vs la señal. |
| Tamaño mínimo | Rechaza si las shares < `orderMinSize` del mercado. |
| Tick rounding | Redondea el precio al `orderPriceMinTickSize` (orden válida). |
| neg-risk | Firma con el flag correcto para mercados neg-risk del Mundial. |

## Estado actual (al 2026-06-20)

- Pipeline live **operativo en dry-run**, validado con cuotas reales de Gamma
  (token_id/condition_id/neg_risk/tick reales).
- **Ningún AUTO dispara aún**: inicio de grupos, equipos con 1 partido jugado →
  confianza LOW → todo REVIEW. AUTO empezará a disparar cuando los equipos lleven
  ≥2 partidos completados e ingestados (correr `update_espn.py` + re-migrar al día).

## Pendientes para producción robusta

- **Reconciliación de bankroll/posiciones** con la wallet real (hoy el estado local
  usa un bankroll parámetro; idealmente leer balance + posiciones del CLOB).
- **Scheduler** (cron/Celery) que corra `place_bets.py` en la ventana previa a cada
  partido y refresque el modelo (`update_espn.py` + migración) a diario.
- **Order management**: cancelación/reintento, fills parciales, confirmación on-chain.
