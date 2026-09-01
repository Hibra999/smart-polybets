# 2026-07-14 — Hipótesis de sesgo en Polymarket para Liga MX

## Hipótesis

El flujo recreativo puede sobrecomprar al favorito, mientras que la probabilidad de
empate de una liga de fútbol reduce su probabilidad real de ganar a 90 minutos.

## Lo que sí está medido

- El modelo de cierre histórico supera a Elo/Poisson en varias métricas.
- Liga MX promedió 3.10 goles por partido en la muestra 2025/26.
- La liquidez y el spread de Polymarket deben medirse por jornada; no se presuponen.

## Prueba requerida

1. Grabar bid, ask, spread y profundidad con `record_market_ticks.py`.
2. Comparar Polymarket contra Poisson y precio de cierre.
3. Medir fills, fees y deslizamiento reales en dry-run o sizing experimental aprobado.
4. Evaluar varias jornadas antes de proponer cambios de estado o sizing.

Conclusión: el sesgo es una hipótesis, no edge probado. Las estrategias de Liga MX
permanecen `draft`.
