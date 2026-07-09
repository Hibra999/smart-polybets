# Hallazgo: colocación live de totales — tick 0.0025 + regla de 90' (y traza de la operación)

**Fecha:** 2026-07-09 (PDC) · **Área:** `venue/gateway` (SDK), `execution/`, estrategia knockout
**Contexto:** cuartos de final WC 2026. Primer intento del sistema de colocar apuestas de
**totales** (O/U) en vivo — la pipeline de estrategia solo cubre ganador (ver CLAUDE.md).

## Hallazgo 1 — Mercados "Will X win" de knockout resuelven a 90 minutos

Descripción textual del mercado (France vs Morocco, QF 2026-07-09):

> "This market refers only to the outcome within the first 90 minutes of regular play plus
> stoppage time."

- Empate al 90' → "Will X win" resuelve **No** aunque X avance por penales; el mercado de
  draw resuelve **Yes**. Los O/U y BTTS también son a 90'.
- **Consecuencia para el modelo:** el blend Elo/Bayes/TrueSkill no modela el empate →
  sobreestima P(win) en knockout. Caso real: blend France 71.5% vs mercado 61.1%
  (edge aparente +10.4%), pero el Poisson 1X2 daba 56.0% con empate 24.0% (≈ mercado 25.1%)
  → la apuesta estaba **cara** (−5%), no barata. El edge del blend era fantasma.
- **Regla:** para mercados a 90' en eliminatorias, el yardstick es el **Poisson**
  (`wc_poisson_suggestions.py`), no el blend. Sección nueva en CLAUDE.md.

## Hallazgo 2 — SDK: tick 0.0025 no soportado hasta 0.1.0b12

- Los mercados de **totales** WC (O/U, BTTS, spread, córners) usan `minimum_tick_size=0.0025`
  (confirmado vía Gamma metadata Y vía endpoint CLOB `/tick-size`). Los de ganador usan 0.01
  — por eso este bug nunca apareció al apostar winners.
- Con `polymarket-client==0.1.0b11`, **todos** los paths fallan con
  `UnexpectedResponseError: Unsupported tick size received: 0.0025`:
  `place_limit_order`, `place_market_order` y hasta `estimate_market_price` (read-only).
  Causa: `polymarket/_internal/actions/orders/context.py::_ROUNDING_BY_TICK` solo mapea
  {0.1, 0.01, 0.001, 0.0001}. El SDK re-consulta el tick al servidor, así que forzar otro
  tick en el `TradeOrder` NO ayuda (verificado).
- **Fix:** `pip install --pre -U polymarket-client` → `0.1.0b16`. El changelog de `0.1.0b12`
  dice textualmente: *"Support CLOB order tick sizes 0.005 and 0.0025."*
  (https://docs.polymarket.com/dev-tooling/python)
- Post-upgrade validado: `scripts/account.py` sigue OK y `estimate_market_price` acepta los
  3 tokens. NO parchear `_ROUNDING_BY_TICK` en runtime (se intentó y se revirtió; el camino
  correcto es actualizar el SDK).

## Hallazgo 3 — Artefacto de display en posiciones recién abiertas

`scripts/account.py` muestra `ENTRY 0.00` y computa todo el valor de mercado como uPnL
(ej. "+57.83" inmediatamente después de comprar ~$58) para posiciones recién abiertas.
Es cosmético (la fuente no trae aún el avg_entry_price), pero **engañoso**: el uPnL real
recién abierta la posición es ≈ 0. Pendiente: arreglar el account_source para derivar el
entry del fill cuando el API lo reporte 0.

## Traza de la operación (registro manual — la ruta manual bypassa el LocalState)

Colocadas 2026-07-09 ~15:40 PDC vía `scripts/place_totals_qf.py --live` (SDK 0.1.0b16,
limit GTC al best ask, fill completo inmediato, wallet proxy `0x3198…e442`):

| Mercado | Lado | Precio | Stake | Shares | order_id |
|---|---|---|---|---|---|
| Argentina vs. Switzerland: O/U 2.5 | Over | 0.4175 | $22 | 52.69 | `0xf6dd001ed557f7db…` |
| Norway vs. England: O/U 2.5 | Over | 0.5550 | $22 | 39.64 | `0x624f9b60836ee7ef…` |
| Spain vs. Belgium: O/U 2.5 | Under | 0.4600 | $14 | 30.43 | `0x6634bf9247f8930b…` |

- **Tesis:** edges Poisson vs mercado: Arg-Sui Over +19.2% (modelo 60.8% vs 41.6%),
  Nor-Eng Over +16.4% (71.8% vs 55.4%), Spa-Bel Under +9.4% (55.3% vs 45.9%).
  Sizing ≈ ½ quarter-Kelly por: knockout tiende a menos goles que la base del Poisson,
  partido único ruidoso (sin alineaciones), drawdown semanal (−128 equity).
- **Descartadas a propósito:** France ML (cara por Poisson una vez aplicada la regla de 90'),
  BTTS Yes de los mismos partidos (correlacionadas con los Over — una tesis de goles por
  partido), Marruecos-no-gana (−6%), córners (sin modelo).
- Cash: 528.98 → 470.08. Los BTTS/spread/córners quedan sin modelo — posible extensión
  de estrategia futura (`bet_type: totals`).
