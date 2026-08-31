# Repository Guidelines

## Project Structure & Module Organization

This Python 3.11 project uses flat, top-level packages. The main pipeline flows through `research/`, `risk/`, `optimization/`, `execution/`, `portfolio/`, and `editorial/`. Shared schemas and utilities live in `core/`; tournament configuration and strategies live under `tournaments/<tournament_id>/`. All Polymarket access must go through `venue/`—do not call an SDK directly from scripts or domain packages. Command-line entry points are in `scripts/`, canonical database DDL and ingest data are in `data/`, documentation is in `docs/`, and tests are split between `tests/unit/` and `tests/integration/`.

## Build, Test, and Development Commands

```bash
pip install -e ".[dev]"             # editable install with pytest, coverage, and Ruff
pytest                              # run the configured test suite quietly
pytest tests/unit/test_kelly.py     # run one focused test module
ruff check .                        # lint all Python sources
python scripts/build_db.py --tournament liga_mx_2026 --sport football
```

Optional integrations use `pip install -e ".[optimize]"` or `pip install -e ".[live]"`. There is no separate build step for normal development.

## Coding Style & Naming Conventions

Use four-space indentation, Python 3.11 syntax, and a 100-character line limit. Follow Ruff and existing code patterns: `snake_case` for modules, functions, and variables; `PascalCase` for classes and Pydantic models; `UPPER_SNAKE_CASE` for constants. Keep pure logic in `functions/`, contracts in `schemas/`, and CLI orchestration in `scripts/`. Preserve the one-way domain flow documented in `README.md`.

## Testing Guidelines

Pytest discovers `tests/` automatically. Name files `test_<behavior>.py` and tests `test_<expected_result>`. Prefer deterministic unit tests, in-memory SQLite, existing fixtures from `tests/conftest.py`, and no network access. Add a focused regression test for behavior changes, then run the full suite. No numeric coverage threshold is configured.

## Commit & Pull Request Guidelines

History follows Conventional Commit-style subjects such as `feat:`, `fix(scope):`, `docs:`, and `chore:`. Keep commits focused and imperative. Pull requests should explain the behavior change, affected tournament or pipeline area, validation commands, and any data or live-trading risk. Link relevant issues or design documents; include screenshots only for generated HTML/report changes.

## Security & Configuration

Copy `.env.example` locally and never commit `.env`, private keys, wallet credentials, or generated local databases. Trading is dry-run by default. Do not weaken the required `--live`, `POLYMARKET_LIVE=1`, credential, kill-switch, and typed-confirmation gates; consult `EXECUTION_GOLIVE.md` before touching live execution.
