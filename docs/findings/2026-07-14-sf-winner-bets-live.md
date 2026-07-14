# 2026-07-14 — Apuestas de ganador en semifinales (colocación live manual)

## Operación (aprobada por el CIO, opción "a": Spain + Argentina)
Colocadas 2026-07-13 ~23:53 PDC vía `scripts/place_winner_sf.py --live` (ruta manual,
patrón de `place_totals_qf.py`). Ambas LIMIT al best_ask, fill inmediato:

| Mercado | Lado | Shares | Precio | Stake | order_id |
|---|---|---|---|---|---|
| Will Spain win on 2026-07-14? | Yes | 40.00 | 0.300 | $12 | `0x275e17ef…3118c5` |
| Will Argentina win on 2026-07-15? | Yes | 22.22 | 0.315 | $7 | `0x8b1518bf…fb5c38` |

Cash: 470.08 → 450.42 (=$19 stakes + ~$0.66 fees). Verificado en `account.py`
(2 posiciones abiertas).

## Racional (resumen; detalle en 2026-07-13-poisson-sesgo-knockout.md)
- Yardstick para mercados "win a 90'" en knockout = Poisson 1X2 (regla CLAUDE.md),
  con corrección de etapa 0.87 como variante conservadora.
- Spain: P modelo 37.9-39.3% vs ask 0.300 → edge +7.9 a +9.3 pts (EV c/fee +22-26%).
- Argentina: P modelo 36.3-37.1% vs ask 0.315 → edge +4.8 a +5.6 pts (EV +11-14%).
- Sizing: Kelly ¼ sobre bankroll $470 con prob corregida → $12 / $7.
- Descartadas: France win (cara: mercado 40.5% vs modelo ~31%), England win (edge
  muere con el taker fee 5%), empates (sin valor). El ensemble (elo/bayes/blend)
  pickeaba France — mismo patrón de sobreprecio que costó los QF; no se siguió.

## Por qué ruta manual y no pipeline
1. El `side_criterion: blend` de `match_winner_wc_v1` pickearía France (lado equivocado
   según Poisson) — para Spain el pipeline no puede generar la decisión.
2. El sizing aprobado es Kelly-Poisson ($12/$7), no Kelly-blend ($26/$44).
3. `place_bets.py` dry-run marca `status=executed` (gotcha conocido).
⚠️ Consecuencia: NO estaban en `LocalState` al colocarse. **Actualización 2026-07-14**:
retro-registradas en el ledger vía `scripts/backfill_manual_trades.py` (junto a los 5
totales previos), y desde hoy este escenario va por el carril CIO override
(`propose_bet.py` → `orders.py`), ver CLAUDE.md § "Apuestas manuales".

## Pendiente al resolverse (14/15-jul)
- `update_results.py --apply` tras cada partido + insertar fixtures de final/3er puesto
  (ver 2026-07-13-bracket-sin-semifinales.md).
- Resultado: **Spain GANÓ 0-2 (2026-07-14) → +$28.00** (40 shares @ 0.30, payout $40;
  penal convertido ~min 17 y gol tardío; cuenta pasó de -70.62 a -42.62 neto).
  Argentina: pendiente (15-jul). El partido completo quedó capturado en
  `data/fifa_world_cup_2026/events/2026-07-14-france-vs-spain/ticks.sqlite`
  (378 ticks 1/min + 1,539 lecturas finas 5s — incluye el episodio del penal).
