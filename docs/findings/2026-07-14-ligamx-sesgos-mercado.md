# 2026-07-14 — Sesgos de mercado en Liga MX: dónde puede haber edge (y dónde NO)

Datos: MEX.csv desde 2021/22 (1,700 partidos; Pinnacle closing 88%, Avg/Max 100%,
Betfair Exchange 37%). Reproducción: bloque en este finding / sesión 2026-07-14.

## Exp 1 — ⚠️ "Precio de exchange mejor que el sharp" es una TRAMPA, no un edge
Estrategia naive: apostar en el exchange (Betfair closing) cuando la prob justa de
Pinnacle (devigged) × cuota del exchange da EV>0 (neto de comisión 5%):
| Umbral | Apuestas | ROI |
|---|---|---|
| EV>0.00 | 172 | **-29.6%** |
| EV>0.02 | 112 | **-44.8%** |
| EV>0.05 | 56 | **-62.2%** |
**El precio "barato" mostrado en un exchange vs el sharp suele ser stale o de libro
fino — cuanto más "barato", peor.** Consecuencia directa para Polymarket: la
hipótesis "PM es blando" NO se valida mirando el precio mostrado vs cierre; hay que
verificar profundidad/ejecutabilidad por mercado. El tracker J1-J3 debe registrar
**spread y depth del book de PM**, no solo el precio.

## Exp 2 — Sesgo favorito-longshot: robusto y direccional
ROI ciego por bucket de prob. implícita del cierre:
| Bucket | Avg (cierre promedio) | Max (mejor cuota) |
|---|---|---|
| <20% (longshots) | **-21.4%** (n=448) | **-13.4%** (n=621) |
| 20-35% | -10.4% | -1.5% |
| 35-50% | -4.9% | -2.6% |
| ≥50% (favoritos) | -2.1% | **+2.7%** (n=751) |
Por rol (Avg): favorito -4.5% · empate -5.6% · underdog **-16.4%** · local -7.8% ·
visita -13.1%.
- El gradiente es monótono y consistente en ambas escalas de precio → el sesgo
  clásico favorito-longshot EXISTE en Liga MX.
- El +2.7% de favoritos a mejor precio NO es significativo por sí solo
  (σ≈3.5% con n=751), pero la dirección sí: **el lado longshot/empate está
  estructuralmente caro; el lado favorito a buen precio es el único con ROI ~0/+**.

## Implicaciones operativas (Polymarket)
1. **Nunca comprar longshots ni empates a precio de retail** en PM (el flujo retail
   los infla — es donde el -13/-21% vive). "Vender" un longshot caro = comprar el
   lado No.
2. **El lado favorito a precio ≥ mejor cuota del mercado** es el único patrón
   históricamente ~breakeven/positivo sin modelo. Regla candidata: solo tomar
   favoritos cuando el precio de PM sea MEJOR que el Max de las casas.
3. **Colocación de órdenes (edge de ejecución, independiente del modelo)**: los
   mercados deportivos de PM cobran ~5% taker sobre ganancias y pagan REBATE al
   maker (`fee_schedule.rate=0.05 taker_only, rebate_rate=0.15`). Política
   maker-first: postear LIMIT dentro del spread (GTC con cap) en vez de cruzar,
   y cruzar solo cerca del kickoff. En mercados nuevos/ilíquidos (Liga MX) el
   spread es ancho: capturarlo en vez de pagarlo puede valer más que el edge de
   modelo que no tenemos. PENDIENTE: cuantificar con nuestros 37 trades del WC
  (descomponer PnL en modelo vs fees vs spread) y con `list_trades` del SDK.

## Backtests adicionales posibles con los datos actuales
- **Dixon-Coles** (corrección de empates del Poisson): 4.6k partidos alcanzan.
- **WC retrospectivo**: tabla `polymarket_odds` (PM + Codere) + price history del
  SDK → ¿PM estaba blando vs libros durante el Mundial? Medible YA.
- **Análisis de nuestros propios fills** (37 trades WC): costo real de ejecución.
- NO backtesteable con MEX.csv: totales/O-U (no trae líneas), movimiento de línea
  (solo trae cierre).
