#!/usr/bin/env python
"""Genera la presentacion HTML de la arquitectura del sistema (audiencia general).

    python scripts/architecture_deck.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from editorial.functions.architecture_deck import build_architecture_deck
from editorial.functions.report_builder import save_report


def main() -> None:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = build_architecture_deck(gen)
    path = save_report("_system", html, suffix="architecture_deck", ext="html")
    print(f"Presentacion: {path}")


if __name__ == "__main__":
    main()
