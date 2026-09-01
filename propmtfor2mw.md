# Prompt de continuación para Codex

Trabaja autónomamente dentro del repositorio:

`/home/gabo/portfolio/projects/37-pepa`

## Fecha de ejecución

Obtén la fecha UTC real al empezar. La continuación prevista es 2026-09-02 UTC, pero no
la asumas.

## Objetivo

Continúa la investigación, implementación, validación y publicación de `smart-polybets`
desde el estado real del worktree.

Busca evidencia de rentabilidad robusta fuera de muestra para Liga MX o NFL, pero:

- no inventes resultados;
- no hagas p-hacking sobre 2025;
- no llames robusto a un ROI agregado que falla por temporada;
- no promociones modelos o thresholds por un solo backtest;
- no declares EV neto sin fee y slippage;
- si aún no existe evidencia robusta, conserva los resultados negativos y explica el
  límite de datos exacto.

No te limites a dar un plan: ejecuta el trabajo seguro y verificable hasta completarlo.

## Autonomía

Opera en full-auto y no pidas confirmaciones conversacionales para acciones normales del
repositorio, red pública, tests, commits, push o GitHub Actions.

Esta autonomía NO autoriza mover dinero.

## Prohibido

- Órdenes reales, cancelaciones o approvals financieros.
- `--live` en scripts de ejecución de apuestas.
- Modificar `POLYMARKET_LIVE`, kill-switch, allowance, signer o credenciales.
- Operar Liga MX; permanece `draft`.
- Operar NFL; todo sigue siendo dry-run.
- Mundial, otras ligas, props, parlays, futuros o in-play.
- Force-push o reescritura de historia.
- Ajustar thresholds después de mirar el holdout 2025.

`scripts/generate_reports.py --live` sí está permitido: únicamente lee mercados
públicos.

## Instrucciones obligatorias

Antes de modificar nada, lee completamente:

1. `AGENTS.md`
2. `INIT.md`
3. `README.md`
4. `EXECUTION_GOLIVE.md`
5. `docs/PROMPTS.md`
6. Los `SKILL.md` de las áreas tocadas
7. `tournaments/registry.py`
8. Los `TOURNAMENT.md` y `STRATEGY.md` activos
9. `docs/findings/2026-09-01-sota-ligamx-nfl.md`

En conflictos manda:

seguridad → AGENTS.md → código/tests → registry → estrategia → documentación.

## Alcance canónico

Sólo deben existir:

- `liga_mx_2026`: estrategia `draft`, observación y dry-run.
- `nfl_2026`: estrategia `approved`, pero dry-run en esta misión.

Flujo obligatorio:

`Research → Risk → Optimization → Execution → Portfolio → Editorial`

Todo acceso a Polymarket debe pasar por `venue/`.

## Estado de continuación — verificar, no asumir

Último commit remoto conocido:

- rama: `main`
- SHA: `a1ddb59394dccdffaff5207b7820f07550b9c6a5`
- identidad requerida: `Hibra999 <miarsito1@gmail.com>`
- SSH key requerida: `/home/gabo/.ssh/id_ed25519_hibra999`

Hay cambios locales importantes todavía sin commit. Presérvalos y audítalos con
`git status`, `git diff`, `git diff --cached` y archivos no rastreados.

Cambios conocidos:

- Historia NFL ampliada a 2010–2026.
- La estrategia TrueSkill activa permanece anclada a 2022 mediante
  `ACTIVE_HISTORY_START` / `in_active_history`.
- `fetch_game_stats.py` procesa PBP año por año para evitar concatenar todo en memoria.
- Se corrigió `_kickoff` de nflverse: `gametime` está en Eastern Time y ahora se convierte
  a UTC respetando DST.
- Nuevo colector `scripts/nfl_polymarket_history.py`.
- Nuevo test `tests/unit/test_nfl_polymarket_history.py`.
- Dataset público: `data/nfl_2026/ingest/polymarket_t24h.csv`.
- Reporte: `editorial/reports/nfl_2026/2026-09-01_pm-history.json`.
- Se actualizó: `docs/findings/2026-09-01-sota-ligamx-nfl.md`.
- Se regeneró: `docs/assets/sota-validation-pipeline.png`.
- `daily_suggestions.py` y el HTML ahora deben usar:
  - `SIMULATED_BUY` sólo para `AUTO` accionable;
  - `NO_TRADE` para `REVIEW`, `DISCARD` y `SKIP`;
  - condition ID, token ID, outcome, best ask, volumen, liquidez, tick y mínimo.
- Los HTML publicados locales fueron regenerados bajo
  `editorial/reports/_system/published/`.

El último `apply_patch` fue interrumpido. Verifica si quedaron aplicados parcial o
totalmente estos cambios antes de repetirlos:

- Renombrar `CURRENT_SPORTS_TAKER_FEE_BPS` a `BACKTEST_FEE_SCENARIO_BPS`.
- Aclarar en `INIT.md` que 500 bps es sólo un escenario histórico.
- Aclarar en el finding que la tasa live siempre se consulta por token.
- Añadir el resultado negativo de la calibración Platt.

No dupliques ni sobrescribas a ciegas.

## Evidencia ya obtenida

Datos NFL locales después de la ampliación:

- 4,363 fixtures finalizados, temporadas 2010–2025.
- 272 fixtures NFL 2026 scheduled.
- 8,726 registros `match_team_stat`.
- 3,197 jugadores.
- PBP 2026: `partial`, aún no publicado.
- Injuries 2026: `partial`, sin imputación.
- Freshness pasó para Liga MX y NFL.
- No había fixtures pasados todavía marcados `scheduled`.

Liga MX:

- 4,700 partidos, 15 temporadas aproximadamente.
- El mercado de cierre de-vig continúa ganando en log-loss.
- Holdout 2025/26, n=336:
  - market-only: log-loss 0.9774, Brier-3 0.19391;
  - Dixon-Coles: 0.9957 / 0.19802;
  - Poisson: 1.0054 / 0.20028;
  - market+features: 1.0017 / 0.19944.
- Gate `FAIL`; Dixon-Coles sigue siendo challenger.
- OO-EPC y FL-GLM se reprodujeron, pero no dieron beneficio estable.
- No cambies el blend Elo+Bayes ni el status `draft`.

NFL SOTA:

- Train 2022–2023, calibración 2024, holdout 2025.
- n train/cal/test: 414/208/208.
- Market-only:
  - log-loss 0.66534256;
  - Brier 0.46489526;
  - ECE 0.12336427.
- Challenger ratings+EPA:
  - log-loss 0.70460591;
  - Brier 0.49310756;
  - ECE 0.14156727.
- Delta `market − challenger`: −0.03926335.
- Bootstrap IC 95%: [−0.06520773, −0.01256042].
- Gate `FAIL`; no promoción.

Histórico Polymarket NFL T-24h:

- El catálogo público empieza el 8 de agosto de 2024; no se encontraron temporadas
  anteriores.
- 525 contratos moneyline exactos cruzados.
- 506 snapshots válidos.
- 505 observaciones para calibración.
- La documentación oficial sólo define `price_history` como “historical price data”.
  No afirmes que sea last trade, midpoint o best ask.
- Market-only:
  - log-loss 0.59925264;
  - Brier 0.41254235;
  - ECE 0.03780000.
- TrueSkill activo:
  - log-loss 0.66399865;
  - Brier 0.46611332;
  - ECE 0.05576816.
- Delta `market − model`: −0.06474600.
- Bootstrap IC 95%: [−0.09662677, −0.03509011].
- Replay continuo 2024–2025:
  - bankroll 1,000→1,650.31;
  - ROI +65.03%;
  - yield +4.319%;
  - 255 apuestas;
  - max drawdown 37.835%.
- Por temporada con bankroll reiniciado:
  - 2024: ROI +56.19%;
  - 2025: ROI −43.65%.
- Por tanto, el gate es `FAIL`. No llames robusta a la ganancia agregada.
- No hay best ask, order book ni slippage históricos reconstruibles.
- Los contratos históricos incluidos indicaban fees deshabilitados.

Hipótesis adicional ya probada:

- Calibración Platt del logit del precio, fit sólo en 2024 y test en 2025.
- Market 2025:
  - log-loss 0.610361;
  - Brier 0.424052;
  - ECE 0.034921.
- Platt:
  - log-loss 0.614362;
  - Brier 0.427320;
  - ECE 0.055412.
- Bankroll 1,000→987.69.
- ROI −1.23%, 76 apuestas.
- Descartada. No buscar thresholds sobre ese mismo holdout.

Backtests canónicos más recientes:

Liga MX 2026/27:

- bankroll 1,000→938.95;
- ROI −6.105%;
- yield −18.784%;
- 13 apuestas, 5W–8L;
- win rate 38.46%;
- max drawdown 7.838%;
- fees 8.30 bajo escenario de 500 bps;
- fuente: football-data.co.uk AvgC closing;
- slippage histórico no disponible.

NFL 2025:

- bankroll 1,000→357.55;
- ROI −64.245%;
- yield −13.391%;
- 96 apuestas, 44W–52L;
- win rate 45.83%;
- max drawdown 70.09%;
- fees 116.40 bajo escenario de 500 bps;
- fuente: nflverse closing moneyline;
- slippage histórico no disponible.

## Mercado live observado — reconsultar porque caduca

El 2026-09-01 los cuatro tokens Liga MX disponibles devolvieron:

- best asks: 0.60, 0.50, 0.56 y 0.29;
- `base_fee=1000` bps en los cuatro;
- profundidad suficiente al mejor ask para el tamaño mínimo;
- todos quedaron `DISCARD` por volumen insuficiente y uno además por edge negativo;
- NFL no tenía cuota para su próximo fixture y quedó `SKIP`.

La tabla general oficial mostraba Sports `feeRate=0.05`, pero el endpoint específico
`/fee-rate` devolvió 1000 bps. Registra ambos hechos, usa el valor específico por token
para el snapshot actual y no conviertas ninguna de las dos cifras en constante live.

No calcules edge neto si falta slippage o cualquier coste requerido.

## Tareas de mañana

1. Audita worktree, rama, remoto, identidad y cualquier proceso residual.
2. Inspecciona todos los diffs antes de editar; preserva cambios del usuario.
3. Completa o corrige el patch interrumpido sobre el escenario de fees.
4. Actualiza datos únicamente según `INIT.md`:
   - Liga MX fixtures/resultados/historia.
   - NFL schedule desde 2010, después PBP por año y roster/depth chart.
   - Si PBP o injuries 2026 siguen ausentes, conserva `partial`.
5. Ejecuta `scripts/check_freshness.py`.
6. Regenera el histórico Polymarket sólo si es necesario:
   `.venv/bin/python scripts/nfl_polymarket_history.py --refresh`
7. Reejecuta los experimentos SOTA canónicos.
8. No pruebes más variantes sobre el holdout 2025 salvo una hipótesis nueva,
   predefinida y justificada antes de ver su resultado. Registra el número de intentos.
9. Prioriza conseguir un periodo realmente no visto o comenzar captura forward de:
   best ask, profundidad, fee, settlement y slippage.
10. Obtén las próximas fechas desde SQLite, no desde texto histórico.
11. Regenera reportes live:

    ```bash
    .venv/bin/python scripts/generate_reports.py --bankroll 1000 \
      --publish-dir editorial/reports/_system/published --live
    ```

12. Para cada token actual consulta:
    - condition ID;
    - token ID;
    - pregunta/outcome/reglas;
    - best ask y tamaño;
    - tres niveles del ask;
    - volumen y liquidez;
    - tick y mínimo;
    - `base_fee`.
13. No llames EV positivo a edge bruto.
14. Ejecuta:
    - pruebas afectadas;
    - suite completa;
    - Ruff sobre archivos afectados;
    - `git diff --check`;
    - comprobación de sólo dos torneos;
    - escaneo de secretos, `.env`, SQLite y archivos temporales.
15. Revisa visualmente ambos HTML.
16. Crea commits descriptivos y sube `main` a `origin`, sin force-push.
17. Monitoriza `.github/workflows/reports.yml` hasta estado terminal.
18. Verifica HTTP 200 y corte UTC actualizado:
    - https://hibra999.github.io/smart-polybets/
    - https://hibra999.github.io/smart-polybets/backtest.html
19. Finaliza con worktree limpio y confirma SHA local/remoto.

## Gate de rentabilidad

Un challenger sólo puede proponerse para revisión si simultáneamente:

- supera `market-only` en log-loss con bootstrap IC 95% completamente positivo;
- Brier no empeora;
- ECE no empeora más de 0.01;
- ROI y yield son positivos después de fees y slippage;
- existen al menos 300 decisiones liquidadas fuera de muestra;
- es positivo y estable por temporada y segmento;
- no depende de un único año;
- no faltan datos críticos;
- se declara el número de hipótesis/modelos probados.

Cumplir el gate sólo autoriza revisión humana. Nunca autoriza una orden.

## Formato de entrega

Empieza por el resultado.

Incluye:

1. Pages: ambas URLs, HTTP, fecha del contenido y workflow.
2. Frescura por fuente, registros y datasets `partial`.
3. Predicciones por fixture con modelos, señal activa, P_model, best ask, edge bruto,
   fee, slippage, confianza, muestra, verdict, acción y stake.
4. Backtest por torneo con comando, temporada, bankroll, precios, muestra, ROI, yield,
   win rate, drawdown, fees, slippage y HTML.
5. Evaluación SOTA y gate completo.
6. Cambios de ingeniería, tests, commits, rama y SHA remoto.
7. Riesgos comprobados y siguiente dato realmente necesario.
8. Confirmación explícita:
   - cero dinero movido;
   - Liga MX continúa `draft`;
   - NFL continúa dry-run;
   - ningún challenger fue promovido.

No ocultes pérdidas ni prometas vencer al mercado.

Importante: el trabajo anterior probablemente sigue sin commit. Comienza auditando y
conserva ese worktree; no asumas que partes del SHA remoto limpio.
