# 2026-07-14 — EDA de minutos de gol Liga MX 2025/26

Fuente: partidos 2025/26 de football-data.co.uk usados por
`scripts/ligamx_goal_eda.py`.

## Hallazgos

- 3.10 goles por partido.
- El favorito anotó antes del minuto 30 en 37% de los partidos.
- El intervalo 76–90 fue el más denso.
- Hubo tarjetas rojas en 34% de los partidos; mediana del minuto de roja: 74.

## Implicación para theta_lay_v1

El riesgo de un gol temprano y la actividad tardía hacen que `hard_exit_min=105` y
`from_min=30` sean parámetros provisionales. Antes de aprobar la estrategia se debe
probar con ticks propios:

- salida dura entre minutos 60 y 75;
- take-profit habilitado entre minutos 20 y 25;
- salida ante roja al no favorito y revisión ante roja al favorito.

El finding no autoriza live ni cambia el estado `draft`.
