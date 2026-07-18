#!/usr/bin/env python
"""check_strategy_evolution.py — verifica que cada STRATEGY.md tenga su EVOLUTION.md al
día (la última entrada [FORMAL] declara la misma version). Advisory: exit 2 si hay drift.

    python scripts/check_strategy_evolution.py
    python scripts/check_strategy_evolution.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8  # noqa: E402

enable_utf8()

import core.strategy_evolution as se  # noqa: E402


def run(as_json: bool = False) -> int:
    results = se.evaluate_all()
    drift = [r for r in results if not r.ok]
    if as_json:
        print(json.dumps({"ok": not drift,
                          "results": [r.model_dump(mode="json") for r in results]},
                         indent=2, default=str))
    else:
        print("\n=== Evolución de estrategias ===")
        for r in results:
            print(f"  {'OK ' if r.ok else '!! '}{r.strategy_id}: {r.detail}")
            if not r.ok and r.remedy_cmd:
                print(f"        → {r.remedy_cmd}")
        print(f"\n  {'TODO AL DÍA' if not drift else 'HAY DRIFT — registrá la evolución'}\n")
    return 0 if not drift else 2


def main() -> None:
    ap = argparse.ArgumentParser(description="Validador de evolución de estrategias.")
    ap.add_argument("--json", action="store_true")
    sys.exit(run(ap.parse_args().json))


if __name__ == "__main__":
    main()
