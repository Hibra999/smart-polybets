"""check_freshness.py — reporta el estado de las precondiciones de datos.

    python scripts/check_freshness.py          # resumen legible
    python scripts/check_freshness.py --json    # JSON (cron/hooks)

Exit code 2 si hay alguna violación mandatoria; 0 si no. Read-only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()

import core.preconditions as pc
from tournaments.registry import TOURNAMENTS


def run(as_json: bool = False) -> int:
    results = pc.evaluate("READ", tournaments=list(TOURNAMENTS))
    violations = [r for r in results if r.is_violation]
    if as_json:
        print(json.dumps({
            "ok": not violations,
            "results": [r.model_dump(mode="json") for r in results],
        }, indent=2, default=str))
    else:
        print("\n=== Frescura de datos (Liga MX y NFL) ===")
        if not results:
            print("  (no hay torneos activos por fecha)")
        for r in results:
            mark = {True: "OK ", False: "!! ", None: "?? "}[r.ok]
            tid = f"[{r.tournament_id}] " if r.tournament_id else ""
            print(f"  {mark}{r.name}: {tid}{r.detail}")
            if r.remedy_cmd and r.ok is not True:
                print(f"        → {r.remedy_cmd}")
        print(f"\n  {'TODO AL DÍA' if not violations else 'HAY DATOS VIEJOS — refrescá antes de operar'}\n")
    return 0 if not violations else 2


def main() -> None:
    ap = argparse.ArgumentParser(description="Estado de precondiciones de datos.")
    ap.add_argument("--json", action="store_true")
    sys.exit(run(ap.parse_args().json))


if __name__ == "__main__":
    main()
