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
│       ├── match_winner_wc_v1/STRATEGY.md (approved, activa)
│       ├── match_winner_v1/STRATEGY.md    (approved)
│       └── top_scorer_v1/STRATEGY.md      (draft)
├── liga_mx_2026/
│   ├── TOURNAMENT.md
│   ├── adapter.py
│   └── strategies/
│       ├── match_winner_ligamx_v1/STRATEGY.md (draft)
│       └── theta_lay_v1/STRATEGY.md           (draft, trading intra-partido)
└── nfl_2026/
    ├── TOURNAMENT.md
    ├── adapter.py
    └── strategies/
        └── game_winner_v1/STRATEGY.md    (draft)
```

## Agregar un torneo (4 pasos, whitepaper §13)

1. Crear el adaptador en `adapters/{sport}/` (o reusar: el de fútbol acepta
   `home_adv_elo` para ligas con localía).
2. Registrar el torneo en `registry.py` (`TOURNAMENTS[...]`) con sus parámetros
   de venue/modelo: `polymarket_tag_id` (discovery/update_results/recorder),
   `neutral_venue` (False = liga con localía → Poisson `neutral=False`) y
   `home_adv_elo` (puntos Elo de localía, calibrar — Liga MX: 80).
3. Crear `tournaments/{id}/` con `TOURNAMENT.md`, `adapter.py` y al menos una
   estrategia en `strategies/{strategy_id}/STRATEGY.md` con `status: draft`.
4. Construir la DB (`scripts/build_db.py`) y poblarla con los scripts de
   `data/{id}/ingest/` (+ `DATA_SOURCES.md` con fuentes y rutina).
   (Django fue retirado — el estado vive en `LocalState`.)

## STRATEGY.md

Es la **única fuente de verdad** de las reglas de trading para una combinación
`torneo × tipo de mercado`. Se parsea a `StrategyConfig` (ver `core/strategy.py`).
Sólo una estrategia con `status: approved` puede operar en modo AUTO.
