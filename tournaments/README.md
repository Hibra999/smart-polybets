# `tournaments/` — Configuración por torneo/liga

El torneo activo es un **parámetro de configuración**, no un supuesto hardcodeado.
Agregar un deporte nuevo = una estrategia nueva + un adaptador de datos. El
pipeline de áreas (Research → Risk → Optimization → Execution → Portfolio →
Editorial) permanece idéntico.

## Estructura

```
tournaments/
├── registry.py            # {tournament_id → TournamentConfig} + get_adapter + load_active_strategy
├── _template/             # plantilla para un torneo nuevo
│   ├── TOURNAMENT.md
│   ├── adapter.py
│   └── STRATEGY.md
├── fifa_world_cup_2026/
│   ├── TOURNAMENT.md
│   ├── adapter.py
│   └── strategies/
│       ├── match_winner_v1/STRATEGY.md   (approved)
│       └── top_scorer_v1/STRATEGY.md     (draft)
└── nfl_2026/
    ├── TOURNAMENT.md
    ├── adapter.py
    └── strategies/
        └── game_winner_v1/STRATEGY.md    (draft)
```

## Agregar un torneo (4 pasos, whitepaper §13)

1. Crear el adaptador en `adapters/{sport}/`.
2. Registrar el torneo en `registry.py` (`TOURNAMENTS[...]`).
3. Crear `tournaments/{id}/` con `TOURNAMENT.md`, `adapter.py` y al menos una
   estrategia en `strategies/{strategy_id}/STRATEGY.md` con `status: draft`.
4. Registrar el torneo en el Django App vía `django_client.register_tournament(...)`.

## STRATEGY.md

Es la **única fuente de verdad** de las reglas de trading para una combinación
`torneo × tipo de mercado`. Se parsea a `StrategyConfig` (ver `core/strategy.py`).
Sólo una estrategia con `status: approved` puede operar en modo AUTO.
