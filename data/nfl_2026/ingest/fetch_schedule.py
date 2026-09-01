"""Reconstruye calendario/resultados NFL desde el dataset oficial nflverse."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.migrate_nfl_data import migrate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", type=int, default=2022)
    parser.add_argument(
        "--target", type=Path,
        default=REPO_ROOT / "data" / "nfl_2026" / "nfl_2026.sqlite")
    args = parser.parse_args()
    for key, value in migrate(args.target, args.since).items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
