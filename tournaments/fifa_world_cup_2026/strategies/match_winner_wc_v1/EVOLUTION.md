# EVOLUTION — match_winner_wc_v1

> Estado actual (2026-07-18)
> **version**: 1.0 · **status**: approved
> **Postura**: activa para bracket restante del Mundial (semis/3er puesto/final).
> Bet_type por defecto `win`; `double_chance` disponible para partidos donde el
> empate a 90' infla el riesgo del pick. El sizing sigue siendo Kelly ¼ sobre el
> blend Elo/Bayes para mercados de fase de grupos; para knockout el yardstick de
> precio correcto es el Poisson 1X2 (NO el blend, ver observación 2026-07-13).
> **Preguntas abiertas**: ¿corregir el Poisson por factor de etapa antes de
> confiar en sus edges de knockout? ¿vale la pena portar Dixon-Coles para el
> empate con la muestra que queda (semis/final)?
> **Próximo paso**: al abrir semis/3er puesto/final en Polymarket, pricear con
> Poisson 1X2 corregido por etapa (0.87), no con el blend crudo.

---

### 2026-07-01 · v1.0 (génesis) · [FORMAL]
**Origen**: migración 1:1 desde `pypro_worldcup_betting` (`worldcup.db`, estrategia
activa **"kelly + blend + filtro no"**: `side_criterion=blend` Elo+Bayes 50/50,
`sizing=kelly` fraccional ¼, `use_bayes_filter=False`, `start_match_no=2`,
backtest yield 21.8% / ROI 19.0% en el repo origen). Mapeo completo componente a
componente en `tournaments/fifa_world_cup_2026/STRATEGY_MIGRATION.md`. Se declaró
`version: 1.0` / `status: approved` desde el día uno porque la estrategia YA
estaba validada y en producción en el repo origen — no es un draft nuevo, es un
port de algo que ya operaba.

Este ledger se abre en bootstrap (2026-07-18) y absorbe retroactivamente dos
cambios de contenido que NO tocaron `version`/`status` del HEADER (documentación,
no cambio de reglas — por eso no llevan entrada FORMAL propia):
- **2026-07-02** (`3cdddc7`): se documentó explícitamente el campo `bet_type`
  (`win` por defecto, `double_chance` disponible) en el STRATEGY.md — el
  comportamiento ya existía en el parser, esto fue formalizar el HEADER.
- **2026-07-01** (`c6c6074`): baseline previo al subsistema de cuenta live.

### 2026-07-13 · [OBSERVACIÓN]
**Hipótesis**: el blend Elo/Bayes es el yardstick correcto para pricear mercados
"Will X win" en knockout (igual que en fase de grupos).
**Resultado**: falso. Estos mercados resuelven a **90' + descuento**, no al
avance real (un empate que se define por penales resuelve `No`). El blend no
modela el empate → sobreestima sistemáticamente P(gana) en eliminatorias e
infla edges fantasma (ej. France vs Morocco QF: blend daba France 71.5% vs
mercado 61%, pero el Poisson 1X2 —que sí descuenta el empate— daba 56%: la
apuesta estaba CARA, no barata). Investigación más profunda
(`docs/findings/2026-07-13-poisson-sesgo-knockout.md`) encontró además que el
propio Poisson tiene 3 sesgos de sobre-gol/sub-empate en knockout (Qatar 2022
con goles de prórroga contaminando el fit, sin factor de etapa —knockout anota
~18% menos que grupos—, y Poisson independiente sin Dixon-Coles subestimando
el empate ~5-8pp).
**Disposición**: para mercados a 90' en knockout (win, draw, totales, BTTS) usar
el **Poisson 1X2 corregido por etapa** como yardstick de precio, no el blend.
El blend sigue siendo válido para señal de fuerza relativa, no para precio de
"win a 90'" en eliminatorias. No se cambió el `STRATEGY.md` (el `side_criterion`
de la config sigue siendo `blend` para el pick de fase de grupos); el ajuste de
precio en knockout se aplica en el research/pipeline de sugerencias
(`wc_poisson_suggestions.py`), no en la config de la estrategia.
