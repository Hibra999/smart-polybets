# `data/` — Datos crudos por torneo (SQLite)

Cada torneo tiene su propio archivo `.sqlite` **aislado**. Un archivo por torneo
significa que podés borrarlo, reemplazarlo o experimentar sin afectar otros
torneos. Claude Code lo lee directo con `sqlite3` — sin servidor, sin credenciales.

## Organización

```
data/
├── _schema/                      # DDL canónico por deporte (el contrato)
│   ├── football.sql
│   └── american_football.sql
├── fifa_world_cup_2026/
│   ├── fifa_world_cup_2026.sqlite   # generado por scripts/build_db.py (no en git)
│   ├── DATA_SOURCES.md
│   └── ingest/                      # scripts de ingesta de este torneo
└── nfl_2026/
    ├── nfl_2026.sqlite
    ├── DATA_SOURCES.md
    └── ingest/
```

## Construir un SQLite vacío

Los `.sqlite` **no** se versionan en git (ver `.gitignore`). Se construyen desde
el DDL canónico:

```bash
python scripts/build_db.py --tournament fifa_world_cup_2026 --sport football
python scripts/build_db.py --tournament nfl_2026 --sport american_football
```

Luego se poblan con los scripts de `ingest/` de cada torneo (ver el
`DATA_SOURCES.md` correspondiente).

## Regla

- La capa `adapters/` es la **única** que toca estos archivos, y siempre en modo
  **read-only**. Ninguna otra área accede a los datos crudos.
- El "join agentico" entre torneos **no es SQL** — es Python en
  `adapters/football/cross_tournament_joiner.py`.
- El `fixture.id` del SQLite **no** es el `condition_id` de Polymarket.
