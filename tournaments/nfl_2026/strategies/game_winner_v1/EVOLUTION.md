# EVOLUTION — game_winner_v1

> Estado actual (2026-07-18)
> **version**: 1.0 · **status**: approved
> **Postura**: activa como `active_strategy` de `nfl_2026` (`tournaments/
> registry.py`). Modelo TrueSkill puro (μ/σ, sin margen ni empates), sizing
> Kelly fraccional, sembrado con 2022-2025 (1139 juegos) y evaluando 2026
> (272 juegos `scheduled`).
> **Preguntas abiertas**: SÍ existe un backtest de ACIERTO re-corrido en este
> framework (pick "mayor TrueSkill" acertó **168/271 = 62.0%** en la temporada
> 2025 regular, datos nflverse, ver `STRATEGY_MIGRATION.md` §Validación). Lo
> que falta es (a) un backtest de **ROI/edge vs mercado** (el 62% es acierto
> puro, sin comparar contra el precio implícito — a diferencia de la migración
> de worldcup, que trae yield/ROI del origen) y (b) repetir la validación sobre
> la **temporada 2026** una vez haya juegos jugados.
> **Próximo paso**: correr un backtest de ROI/edge vs cierre sobre la
> temporada 2026 (análogo al de Liga MX) antes de escalar sizing.

---

### 2026-07-01 · v1.0 (génesis) · [FORMAL]
**Origen**: migración desde `sports_bet` (modelo TrueSkill 1v1 + sizing Kelly,
`analysis_true_skill.py` / `test_bet_sizing.py`). Mapeo completo en
`tournaments/nfl_2026/STRATEGY_MIGRATION.md`. Diferencias clave vs la migración
de worldcup: solo TrueSkill (sin Elo/Bayes), sin empates
(`draw_probability=0.0`), margen ignorado (actualiza por win/loss, no por
marcador), semilla fresh `N(25, 8.3)` para todos los equipos construida
procesando 2022-2025 en orden cronológico (1139 juegos). Se declaró
`version: 1.0` / `status: approved` desde el día uno, igual que
`match_winner_wc_v1`, porque el modelo+sizing ya operaban en el repo origen —
es un port, no un draft nuevo. Este ledger se abre en bootstrap (2026-07-18);
no hay cambios de `version`/`status` posteriores a registrar — no se ha corrido
todavía un backtest propio de la temporada 2026 en este framework (queda como
próximo paso, no como entrada FORMAL retroactiva).
