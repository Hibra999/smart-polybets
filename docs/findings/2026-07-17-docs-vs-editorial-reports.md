# 2026-07-17 — Dónde vive cada entregable: `docs/` vs `editorial/reports/`

## Síntoma
Reportes HTML de análisis (backtests, EDA, post-mortem de cartera) se venían
guardando sueltos en `docs/` — sin `tournament_id`, sin fecha en el nombre —
cuando existe una convención explícita en `editorial/SKILL.md` que manda
guardarlos en `editorial/reports/{tournament_id}/`. Ese descuido está listado
como **error común** en el propio SKILL.md ("Guardar el reporte sin
tournament_id en el path (rompe la organización por torneo)").

Ejemplos que estaban mal ubicados en `docs/` — **todos reubicados el 2026-07-17**:

| Antes (`docs/`) | Ahora (`editorial/reports/{tid}/`) |
|---|---|
| `portfolio-postmortem.html` | `fifa_world_cup_2026/2026-07-17_portfolio_postmortem.html` (fechado: snapshot) |
| `wc-backtest.html` | `fifa_world_cup_2026/wc-backtest.html` (estable: vivo) |
| `ligamx-backtest.html` | `liga_mx_2026/ligamx-backtest.html` (estable: vivo) |
| `ligamx-goles-eda.html` | `liga_mx_2026/ligamx-goles-eda.html` (estable: vivo) |

Los 3 reportes vivos los generaban scripts con la ruta `docs/` **hardcodeada**
(`wc_backtest.py`, `ligamx_backtest_html.py`, `ligamx_goal_eda_html.py`); se
repuntó el `OUT` de cada uno a `editorial/reports/{tid}/` y se actualizaron las
referencias (CLAUDE.md, findings, el HTML del post-mortem) — si no, la próxima
regeneración los recreaba en `docs/`.

## Regla (criterio de decisión)
La pregunta no es "¿es HTML?" sino **"¿es un REPORTE o un DOC del sistema?"**:

| Tipo | Qué es | Dónde va | Nombre |
|---|---|---|---|
| **Reporte** | Salida del pipeline sobre datos/eventos/torneo: backtests, EDA, sugerencias, post-mortem, digests, narrativa de trades | `editorial/reports/{tournament_id}/` (o `_system/` si es cross-torneo) | ver "nombre" abajo |
| **Doc del sistema** | Documentación de cómo funciona el repo/estrategia, no atada a datos de un evento: manuales, arquitectura, explicación de modelos | `docs/` | libre (`theta-trade-manual.html`, `architecture.html`) |

Discriminador rápido: si el contenido **caduca cuando cambian los datos del
torneo** o **responde "¿cómo fue X evento/semana/torneo?"** → es reporte →
`editorial/reports/`. Si describe **el sistema** y sigue válido aunque no se
juegue nada → es doc → `docs/`.

### Nombre del reporte: fechado (snapshot) vs estable (vivo)
Dos sub-tipos de reporte, con convención de nombre distinta:
- **Snapshot** (foto de un instante: sugerencias diarias, post-mortem, digest
  semanal) → `YYYY-MM-DD_<slug>.{md,html}`. Cada corrida deja un archivo nuevo;
  es el naming de `report_builder.save_report()`. Nadie los referencia por ruta
  fija, así que acumular fechas está bien.
- **Vivo/regenerado en sitio** (backtest, EDA: se sobreescriben con el estado
  actual y **se referencian desde docs estables** — CLAUDE.md, findings,
  STRATEGY.md) → **nombre estable sin fecha** (`wc-backtest.html`). Un nombre
  fechado que cambia en cada corrida rompería esas referencias. El generador
  sobreescribe el mismo archivo. Lo no negociable sigue siendo el **path por
  torneo**, no la fecha en el nombre.

## Matices confirmados
- **HTML es válido.** El SKILL.md decía "los reportes son SIEMPRE en Markdown",
  pero `editorial/functions/` ya genera HTML (`html_report.py`,
  `backtest_html.py`, `weekly_backtest_html.py`, `poisson_report.py`) y
  `editorial/reports/` está poblado de `.html`. La regla real es Markdown **o**
  HTML; lo no negociable es el **path por torneo + fecha en el nombre**.
- **`_system/`** es el subdir de reportes cross-torneo (ya existe:
  `2026-06-21_architecture_deck.html`). El post-mortem de hoy NO fue ahí porque
  su contenido está scopeado a un solo torneo (WC 2026, 39 mercados) → tiene
  `tournament_id` propio.

## Estado de `docs/` tras la limpieza
Quedan SOLO docs de sistema (correctos ahí): `architecture.html`, `models.html`,
`use-cases.html`, `theta-trade-manual.{html,md}`, más `docs/findings/` y
`docs/superpowers/`. Ningún reporte de torneo vive ya en `docs/`.

Regla de verificación: `find docs -maxdepth 1 -name '*.html'` no debe listar
backtests, EDA, sugerencias, post-mortems ni digests — si aparece uno, está mal
ubicado.
