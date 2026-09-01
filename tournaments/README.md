# Torneos soportados

El registro canónico es `tournaments/registry.py` y contiene sólo:

```text
tournaments/
├── liga_mx_2026/
│   ├── TOURNAMENT.md
│   └── strategies/
│       ├── match_winner_ligamx_v1/  # draft; observación
│       └── theta_lay_v1/             # draft; doc-only
└── nfl_2026/
    ├── TOURNAMENT.md
    └── strategies/
        └── game_winner_v1/           # approved; dry-run por defecto
```

Cada `STRATEGY.md` es la fuente de verdad de reglas y límites para su mercado.
`load_active_strategy()` sólo devuelve estrategias `approved` salvo que un flujo
read-only solicite explícitamente `require_approved=False`.

Ambos torneos recorren el mismo pipeline:

```text
Research → Risk → Optimization → Execution → Portfolio → Editorial
```

No se agregan IDs fuera de Liga MX y NFL. Los adaptadores deportivos y los parámetros
de venue/modelo se resuelven desde el registry; los scripts no los hardcodean.
