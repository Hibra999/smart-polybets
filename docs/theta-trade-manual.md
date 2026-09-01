# Manual de operación — Theta trade (lay del favorito con salida anticipada)

Estrategia: comprar el **NO del favorito al kickoff** en mercados "Will X win"
(resuelven a 90') y **salir vendiendo antes de la resolución**, capturando el
decaimiento temporal mientras el partido siga cerrado. Las reglas están en
`tournaments/liga_mx_2026/strategies/theta_lay_v1/STRATEGY.md`.

Sólo está documentada para `liga_mx_2026` y permanece en `draft`. Los ejemplos
`--live` describen el mecanismo, pero no autorizan una operación.

## Paso 0 — Cómo obtener el id del mercado
```bash
python scripts/theta_monitor.py --list                       # winner abiertos de Liga MX
python scripts/theta_monitor.py --list necaxa                # filtrado por substring
python scripts/theta_monitor.py --list --tournament liga_mx_2026
```
Muestra kickoff, question, bid/ask live y el **TOKEN NO** de cada mercado.
Con eso hay dos formas de apuntar al mercado:
- `--market "<substring único de la question>"` — recomendado; resuelve token NO,
  tick y kickoff solo.
- `--token <TOKEN_NO> --kickoff <ISO UTC>` — directo si el matching por texto falla.

## Ciclo completo de un trade
```bash
# 1. (siempre en jornada) el recorder juntando data en paralelo
python scripts/record_market_ticks.py

# 2. ENTRADA al kickoff — comprar el NO del favorito por el carril CIO (con riesgo y ledger)
python scripts/propose_bet.py --market "Will FC Juárez win on 2026-07-17?" \
    --outcome no --stake 10 --model-prob 0.55 --reason "theta lay J1"
python scripts/orders.py --approve <key> --live --confirm 10.00

# 3. MONITOREO + SALIDA — armar el CLI con el fill real
python scripts/theta_monitor.py --market "Will FC Juárez win on 2026-07-17?" \
    --entry 0.42 --shares 23.8 --live
```

## Parámetros del CLI (`theta_monitor.py`)
| Parámetro | Default | Qué hace |
|---|---|---|
| `--list [FILTRO]` | — | lista mercados abiertos (tokens + precios) y sale |
| `--market "TXT"` | — | mercado por substring de la question (usa el token NO) |
| `--token ID` | — | token directo (cualquier mercado de PM); requiere `--kickoff` |
| `--kickoff ISO` | — | kickoff UTC (solo con `--token`) |
| `--entry P` | requerido | precio al que compraste el NO |
| `--shares N` | requerido | shares de NO a vender |
| `--tp PCT` | `0.05` | take-profit sobre costo (0.05 = +5%); es BRUTO — ver fees |
| `--from-min M` | `30` | minuto (wall-clock desde kickoff) desde el cual aplica el TP |
| `--hard-exit-min M` | `105` | venta forzada a ese minuto, pase lo que pase (≈ min 85 de juego) |
| `--stop PCT` | sin stop | stop-loss opcional (ej. `0.25`); ojo: los goles gapean |
| `--interval S` | `5` | segundos entre lecturas del book (~460ms por lectura) |
| `--tournament ID` | `liga_mx_2026` | torneo del registry (para `--market`/`--list`) |
| `--live` | dry-run | habilita venta real (+ `POLYMARKET_LIVE=1` + key + kill-switch) |
| `--confirm N` | interactivo | confirmación no interactiva (= shares exactas) |

## Comandos EN VIVO (tipear + Enter mientras corre)
| Comando | Acción |
|---|---|
| `v` | **HARD STOP manual**: vende YA al best bid (3 reintentos con bid fresco) |
| `p` | imprime resumen de PnL/estado |
| `q` / Ctrl+C | sale **sin** vender (la posición queda abierta y te lo avisa) |

## Qué queda registrado (pase lo que pase)
- Cada lectura (bid/ask/size/PnL) → tabla `theta_tick`; la sesión completa
  (entry, regla, salida, order_id, PnL) → `theta_session`. Ambas en
  `data/<torneo>/market_ticks.sqlite` (WAL — sobrevive cortes).
- Si la venta falla tras los reintentos: imprime el resumen + instrucciones
  (`orders.py --list` para gestionar a mano) y todo queda en la DB.
- **Post-trade**: consultar la cuenta y reconciliar el estado antes de cerrar la sesión.

## Advertencias operativas
1. El TP default (+5%) es **bruto**: el round-trip paga ~5% taker sobre ganancias.
   Calibrar el TP mínimo neto con los ticks grabados de J1 antes de dar tamaño.
2. Gol temprano del favorito = gap en contra sin stop posible → sizing chico.
3. Liquidez in-play de Liga MX: SIN medir todavía — J1 es la prueba. Si el
   `sz` del bid que imprime el monitor es menor que tus shares, la salida
   será parcial: achicar el sizing.
