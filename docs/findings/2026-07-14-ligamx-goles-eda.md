# 2026-07-14 — EDA de minutos de gol Liga MX 2025/26: el theta acá es MÁS peligroso que en el WC

## Datos
- **Fuente nueva**: API pública de ESPN (`mex.1`, JSON sin key) → tabla
  `match_timeline_event` (goles con minuto + **tarjetas rojas**) vía
  `data/liga_mx_2026/ingest/fetch_goal_minutes_espn.py` (idempotente).
  Gotcha de mapeo: ESPN llama "Santos" a Santos Laguna.
- 2025/26 completa: **322 partidos, 999 goles (3.10/partido), 138 rojas**;
  favorito identificado con el cierre de football-data en 321.
- EDA reproducible: `python scripts/ligamx_goal_eda.py`.

## Resultados clave
### Timing de goles (backloaded)
| Bin | 01-15 | 16-30 | 31-45(+) | 46-60 | 61-75 | 76-90(+) |
|---|---|---|---|---|---|---|
| % goles | 12.7% | 12.2% | 20.5% | 15.7% | 15.3% | **23.5%** |
1T 45.4% / 2T 54.6%; los descuentos concentran 164 goles (56 en 45+, 108 en 90+).
Mediana del primer gol: **min 27**. Partidos sin goles: solo 2.2%.

### Supervivencia (el corazón del theta)
| min | P(0-0 vivo) | P(favorito sin anotar) |
|---|---|---|
| 15 | 66.5% | 79.4% |
| 30 | 47.2% | **62.6%** |
| 45 | 29.2% | 46.7% |
| 60 | 14.3% | 31.8% |
| 75 | 9.3% | 23.4% |
| 90 | 5.0% | **18.4%** |

### Rojas: un tercer factor enorme
**34% de los partidos tienen roja** (mediana min 74). Roja al favorito = jackpot
del theta; roja al dog = gap en contra. Volatilidad extra concentrada al final.

## Implicación estratégica (honesta): Liga MX ≠ WC knockouts
La evidencia del WC (+21% a 105min) venía de un entorno de **2.46 goles/partido**
con empates 29%. Liga MX 2025/26: **3.10 goles/partido** y el favorito ya anotó
antes del min 30 en el **37.4%** de los partidos (68.2% antes del min 60).
- **Aguantar hasta el min 105 acá es mucho más riesgoso**: la cola ganadora
  (favorito nunca anota) es solo ~18%, y los goles se concentran justo al final
  (76-90 es el bin más denso) — el peor momento para seguir adentro.
- El decaimiento útil vive **temprano**: entre kickoff y min 45 el favorito no
  anotó en ~47-63% de los casos y el theta corre a favor.
- Hipótesis de reglas a testear con los ticks de J1-J3 (NO cambiar STRATEGY aún):
  a) `hard_exit_min` 60-75 en vez de 105 (salir antes del bin 76-90);
  b) TP más agresivo y `from_min` más temprano (20-25);
  c) salida inmediata si roja al DOG (y aguantar si roja al favorito).
- La decisión final necesita los PRICE PATHS de Liga MX (cuánto theta paga el
  mercado por minuto vs este hazard) → dataset de events/ + J1.

## Pendiente
- Cruzar hazard con los ticks reales de J1 → curva EV(salida en min m) y elegir
  parámetros con datos, no con el default heredado del WC.
- Extender el crawl a 2024/25 si hace falta más n (el script acepta --from/--to).
