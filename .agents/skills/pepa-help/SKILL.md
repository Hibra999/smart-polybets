---
name: pepa-help
description: Show the repository prompt catalog when the user says "Codex, help", asks for help, asks what Codex can do, or requests available prompts for Liga MX and NFL.
---

Read `docs/PROMPTS.md` from the repository root.

Return its prompt catalog grouped into read-only requests, prediction/backtest
requests, development requests, and money-changing requests. Do not execute any
listed prompt. State that Liga MX is observation-only while its strategy is draft,
and that NFL remains dry-run unless the user explicitly authorizes a live action that
passes `EXECUTION_GOLIVE.md`.
