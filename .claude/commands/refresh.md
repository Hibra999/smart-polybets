---
description: Refrescar datos de los torneos (resultados finalizados + fixtures nuevos)
---
Refrescá los datos de los torneos activos siguiendo el protocolo de CLAUDE.md. Si en $ARGUMENTS viene un torneo, refrescá solo ese; si no, todos los activos:

- **FIFA World Cup 2026**: `python scripts/update_results.py --apply` y `python scripts/sync_upcoming_fixtures.py --apply` (⚠️ semis/3er puesto/final se insertan a mano — ver gotcha del bracket en CLAUDE.md).
- **Liga MX Apertura 2026**: `python data/liga_mx_2026/ingest/fetch_fixtures_pm.py --apply` y `python scripts/update_results.py --tournament liga_mx_2026 --apply`.

Después corré `python scripts/check_freshness.py` para confirmar que quede limpio (exit 0). Mostrá qué se finalizó/sincronizó.

$ARGUMENTS
