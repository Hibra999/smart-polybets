# Ejecución en Polymarket — Liga MX y NFL

La ejecución real está desactivada por defecto. Predicciones, scans, backtests e
instalación se hacen sin `--live`.

## Pipeline

```text
fixture y precio → Research → Risk → Optimization → Execution → Portfolio → Editorial
```

Sólo `AUTO` puede llegar al broker. `REVIEW` espera aprobación humana y
`DISCARD`/`SKIP` terminan el flujo. Liga MX está `draft` y no admite live.

## Dry-run

```bash
.venv/bin/python scripts/scan_market.py --tournament liga_mx_2026 \
  --hours 168 --observe-draft
.venv/bin/python scripts/scan_market.py --tournament nfl_2026 --hours 240
.venv/bin/python scripts/place_bets.py --tournament liga_mx_2026 \
  --date YYYY-MM-DD --observe-draft --state /tmp/pepa-ligamx.json
.venv/bin/python scripts/place_bets.py --tournament nfl_2026 \
  --date YYYY-MM-DD --state /tmp/pepa-nfl.json
```

## Gates acumulativos para live

Una orden sólo puede salir cuando todos se cumplen:

1. El usuario autoriza esa acción concreta y conoce stake/pérdida máxima.
2. La estrategia está `approved`; nunca usar `--observe-draft`.
3. Frescura MONEY está OK y no se fuerza sin `--reason` autorizado.
4. Existe `POLYMARKET_PRIVATE_KEY` EVM válida.
5. `POLYMARKET_LIVE=1` y `POLYMARKET_KILL_SWITCH=0`.
6. El comando incluye `--live`.
7. Precio, slippage, tick, tamaño mínimo y allowance pasan validación.
8. El operador introduce la confirmación tipada solicitada por el CLI.

Comprobaciones previas, sin colocar órdenes:

```bash
.venv/bin/python scripts/check_freshness.py
.venv/bin/python scripts/polymarket_check.py
.venv/bin/python scripts/orders.py --list
```

Ejemplo NFL; no ejecutarlo sin la autorización anterior:

```bash
.venv/bin/python scripts/place_bets.py --tournament nfl_2026 \
  --date YYYY-MM-DD --live
```

Una apuesta manual también pasa por el ledger y revisión; nunca se llama al broker
directamente:

```bash
.venv/bin/python scripts/propose_bet.py --tournament nfl_2026 \
  --market "QUESTION" --stake 10 --model-prob 0.55 --reason "JUSTIFICACIÓN" --dry-run
.venv/bin/python scripts/orders.py --approve KEY --live --confirm 10.00
```

## Verificación posterior

- Considera ejecutada una orden sólo si el broker devuelve `status=live`.
- Conserva la idempotency key; no repitas una orden ambigua.
- Reconciliación y cancelación también requieren intención explícita:

```bash
.venv/bin/python scripts/account.py --reconcile
.venv/bin/python scripts/orders.py --cancel ORDER_ID --live
```

Si el resultado es incierto, detente y consulta cuenta/órdenes antes de reintentar.
Nunca pegues secretos ni respuestas autenticadas crudas en logs, Git o chat.
