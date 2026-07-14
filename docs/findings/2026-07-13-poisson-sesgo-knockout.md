# 2026-07-13 — Sesgo del Poisson en knockouts: NO son los empates 2026, son 3 causas verificadas

## Hipótesis evaluada
"Los empates de playoffs entraron al Poisson y sesgaron el modelo." **Parcialmente falso**:
los 1-1 a 90' de los knockouts 2026 (reconstruidos de los mercados More Markets de PM) son
exactamente el observable correcto para mercados a 90' — incluirlos NO es contaminación,
es la parte sana del dataset (empujan las tasas hacia abajo, que es lo que el knockout real hace).

## Sesgos REALES verificados (los tres empujan en la misma dirección: sobre-gol / sub-empate)

### 1. `historical_match` (Qatar 2022) guarda los knockouts CON goles de prórroga
Verificado en la tabla: la final Argentina-France está como **3-3** (a 90' fue 2-2) y
Croatia-Brazil como **1-1** (a 90' fue 0-0). 120 minutos contados como si fueran 90.
El KO de Qatar en la tabla da 3.25 goles/partido — inflado. Afecta 16 de ~148 partidos del
fit, concentrado en los equipos que llegaron lejos (Argentina, France, Croatia, Brazil).
Fix posible: corregir los marcadores de `historical_match` a 90' en `migrate_poisson_history.py`.

### 2. Sin efecto etapa: el fit agrupa grupos y knockouts en una sola media
Datos 2026 (marcadores a 90' de la DB):
- Grupos:   72 partidos, **2.99 goles/partido**
- Knockout: 28 partidos, **2.46 goles/partido** (-18%)
El modelo usa base pooled = 1.41 goles/equipo (2.82/partido) → **sobreestima totales de
knockout ~14%**. Es la causa principal del 0W-5L en apuestas O/U (4 Overs de knockout
perdidos). Ejemplo semis: Eng-Arg Over 2.5 61.8% (modelo) → **52.6%** con factor de etapa
0.87 (= 2.46/2.82); el "edge" del Over contra un ask ~0.56-0.62 era fantasma.

### 3. Poisson independiente subestima el empate (sin corrección Dixon-Coles)
Empates a 90': 2026 KO = 8/28 (**29%**), Qatar KO = 5/16 (31%). El modelo da 23.5%
(Eng-Arg) / 28.6% (Fra-Spa). Subestimar el empate infla P(win a 90') de AMBOS lados
→ mismos edges fantasma que la regla del blend, pero más suaves.

## Impacto en las semis (con corrección de etapa 0.87)
| Partido | Métrica | Modelo | Corregido |
|---|---|---|---|
| Eng-Arg | Over 2.5 | 61.8% | 52.6% |
| Eng-Arg | Argentina win 90' | 37.2% | 36.3% (vs ask 31.4% → edge se achica a ~+5% pre-fees) |
| Fra-Spa | Over 2.5 | 39.1% | 31.3% |
| Fra-Spa | empate | 28.6% | 31.1% |

## Fixes candidatos (no aplicados; en orden de impacto/esfuerzo)
1. **Factor de etapa** en `PoissonGoalsModel.forecast` (o en el pipeline): deflactar lambdas
   por `goles_KO / goles_pool` cuando el fixture es knockout. Barato y ataca la causa #2.
2. **Corregir Qatar a 90'** en la migración (causa #1; 4 goles de ET en el dataset).
3. **Dixon-Coles** (correlación de marcadores bajos) para el empate (causa #3; más trabajo,
   beneficio moderado con muestras chicas).
Cualquier cambio debe preservar pureza del modelo (`adapters/`) y pasar por backtest
(`wc_poisson_backtest.py`) antes de usarse para precio.
