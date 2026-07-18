# EVOLUTION — match_winner_ligamx_v1

> Estado actual (2026-07-18)
> **version**: 0.1 · **status**: draft
> **Postura**: draft — NO operar. Las tres precondiciones técnicas (localía
> calibrada, seeds Elo reales, backtest corrido) están resueltas, pero el
> backtest 2025/26 no mostró edge del modelo vs las cuotas de cierre.
> **Preguntas abiertas**: ¿Polymarket precia peor que el cierre en un mercado
> nuevo (abrió recién el 2026-07-13) y con liquidez baja? Eso es lo único que
> podría justificar operar pese al modelo sin edge — no está medido todavía.
> **Próximo paso**: correr en modo observación durante J1-J3 (registrar precio
> PM vs Poisson vs cierre) y recién con evidencia de que PM es blando, proponer
> aprobación con umbral de edge alto (≥0.10) y sizing chico.

---

### 2026-07-18 · v0.1 (génesis) · [FORMAL]
Borrador clonado de `match_winner_wc_v1` como punto de partida para Liga MX
Apertura 2026. Declara `version: 0.1` / `status: draft` — nunca pasó a
`under_review` ni `approved`. Este ledger se abre en bootstrap y absorbe la
historia previa a este registro (la estrategia nunca operó en vivo, no hay
idempotency keys emitidas con v0.1, así que no hay necesidad de bumpear la
version retroactivamente):
- **2026-07-14** (`62de191`): creación del torneo `liga_mx_2026` y scaffolding
  inicial de la estrategia (localía multi-torneo, resultados genéricos).
- **2026-07-14** (finding `docs/findings/2026-07-14-ligamx-backtest.md`):
  backtest sobre la temporada 2025/26 con condiciones de producción (warmup 3
  fechas + regresión ρ=0.80 entre Apertura/Clausura) — **sin edge vs cierre**
  en ningún umbral de EV probado (≥0.02 a ≥0.15, ROI entre -4.5% y -0.7%, todos
  negativos). Conclusión explícita del finding: la estrategia sigue en `draft`
  porque el modelo solo no gana al mercado eficiente; si hay edge será por
  venue blando (PM nuevo/ilíquido), no medido aún.
- **2026-07-17** (`25a08ee`, `710d9f0`): auditoría de coherencia STRATEGY.md vs
  código — **E3**: se alineó `edge_threshold_auto` de 0.05 a **0.10** en el
  `## SIGNAL DEFINITION` del STRATEGY.md para que el umbral de "proponer
  aprobación" coincida con la recomendación explícita del finding de backtest
  (≥0.10, el único rango con ROI menos negativo, -1.7%, de la simulación de
  apuestas). `edge_threshold_review` no se tocó (sigue en 0.02). Este cambio de
  threshold en cualquier otro momento habría bumpeado la version (regla
  config→bump); acá se absorbe en la génesis porque ocurrió antes de este
  ledger y antes de que la estrategia operara.

### 2026-07-14 · [OBSERVACIÓN]
**Hipótesis**: el ensemble Elo+Poisson (localía calibrada `home_adv_elo=80`,
seeds reales, warmup 3 fechas + regresión ρ=0.80 entre torneos cortos) tiene
edge vs las cuotas de cierre (Pinnacle/B365 promedio) de la 2025/26.
**Resultado**: no. El mercado de cierre gana en todas las métricas (Elo Brier
0.15507 vs 0.15049 del mercado; Poisson 1X2 log-loss 1.0018 vs 0.9820) y la
simulación de apuestas (¼ Kelly, max $25) da ROI negativo en los 4 umbrales de
EV probados. Un experimento adicional de ML (Random Forest / logística
multinomial sobre los mismos features) confirma que no hay información
incremental: Δlog-loss ~0 o negativo sobre el precio de cierre.
**Disposición**: la estrategia se mantiene en `draft`. No se bumpea version
(no hubo cambio de config a raíz de esta observación, más allá del ajuste de
umbral E3 ya absorbido en la génesis). Ver
`docs/findings/2026-07-14-ligamx-backtest.md` para el detalle completo.
