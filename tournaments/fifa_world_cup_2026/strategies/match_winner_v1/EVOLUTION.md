# EVOLUTION — match_winner_v1

> Estado actual (2026-07-18)
> **version**: 0.1 · **status**: approved
> **Postura**: legacy/base — quedó **superada** por `match_winner_wc_v1` como
> `active_strategy` de `fifa_world_cup_2026` (`tournaments/registry.py`). No
> opera; se conserva como plantilla original del `market_type: match_winner`
> (incluye `DRAW` como outcome, a diferencia de la migrada) y como referencia
> de diseño previa a la migración de `pypro_worldcup_betting`.
> **Preguntas abiertas**: ninguna activa — no hay plan de retomarla mientras
> `match_winner_wc_v1` siga vigente.
> **Próximo paso**: ninguno; si se retoma o depreca formalmente, requiere su
> propia entrada FORMAL (cambio de `status`).

---

### 2026-07-01 · v0.1 (génesis) · [FORMAL]
Primera estrategia `match_winner` del repo (base/legacy), escrita antes de la
migración de `pypro_worldcup_betting`. Declara `version: 0.1` / `status: approved`
desde el HEADER original — usa el criterio blend Elo/Bayes de fase de grupos
como tesis (el mercado "sobre-reacciona a narrativas mediáticas" en jornadas
tempranas) y modela `outcomes: [HOME_WIN, DRAW, AWAY_WIN]` (3 vías, a diferencia
de `match_winner_wc_v1` que es binaria win/no-win). No tiene evidencia de
backtest propio registrada en el repo — se sustituyó por la versión migrada
(`match_winner_wc_v1`, con backtest real yield 21.8%/ROI 19.0% del origen) como
`active_strategy` del torneo antes de operar en vivo. Este ledger se abre en
bootstrap (2026-07-18); no hay cambios de `version`/`status` posteriores que
registrar — la carpeta quedó congelada como legacy.
