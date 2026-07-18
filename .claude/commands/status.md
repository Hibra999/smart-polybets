---
description: Bootstrap de sesión — estado del repo, cuenta y oportunidades (solo lectura)
---
Ejecutá el bootstrap de sesión de este repo y resumí en pocas líneas. NO apuestes ni escribas nada:

1. `git log --oneline -5` y `git status -s` — dónde quedó la última sesión.
2. `python scripts/check_freshness.py` — ¿hay datos viejos? Si exit≠0, avisá y ofrecé refrescar (`/refresh`).
3. `python scripts/account.py --closed 300` — equity total (cash + posiciones mark-to-market), posiciones abiertas y PnL neto (línea "RESUELTAS … PnL neto", que es flujo de caja y cuadra con la UI).
4. `python scripts/scan_market.py --hours 48` — oportunidades próximas (dry-run).
