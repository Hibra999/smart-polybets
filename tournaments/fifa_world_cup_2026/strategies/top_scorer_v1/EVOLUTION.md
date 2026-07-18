# EVOLUTION — top_scorer_v1

> Estado actual (2026-07-18)
> **version**: 0.1 · **status**: draft
> **Postura**: draft desde su creación — no es `active_strategy` de ningún
> torneo (`tournaments/registry.py` no la referencia). No hay backtest ni
> evidencia de edge registrada en el repo para el mercado Bota de Oro.
> **Preguntas abiertas**: ¿el xG acumulado + minutos proyectados por avance de
> equipo (la tesis del STRATEGY.md) supera al precio de Polymarket en nombres
> mediáticos? Sin datos de xG por jugador cargados en el repo aún.
> **Próximo paso**: ninguno activo — draft en pausa hasta que haya fuente de
> xG por jugador y un backtest mínimo antes de mover a `under_review`.

---

### 2026-07-01 · v0.1 (génesis) · [FORMAL]
Estrategia base para el mercado `top_scorer` (Bota de Oro), escrita junto con
`match_winner_v1` antes de la migración de `pypro_worldcup_betting` (no tiene
equivalente en el repo origen — es diseño nuevo para este framework). Declara
`version: 0.1` / `status: draft` desde el HEADER original: la tesis (proyectar
goles esperados por jugador vs el ancla mediática del precio de Polymarket) no
tiene evidencia de backtest ni fuente de datos de xG por jugador cargada en el
repo — se mantiene en `draft` sin haber pasado a `under_review`. Este ledger se
abre en bootstrap (2026-07-18); no hay historial de cambios de `version`/
`status` que registrar (nunca se tocó desde su creación).
