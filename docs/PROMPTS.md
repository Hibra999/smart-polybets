# Prompts disponibles para Codex

Escribe uno de estos pedidos en lenguaje natural. `Codex, help` sólo muestra este
catálogo; no ejecuta sus ejemplos.

## Consulta y diagnóstico (read-only)

- `Codex, revisa el estado del repo y la frescura de Liga MX y NFL.`
- `Codex, explícame la arquitectura y qué hace cada etapa.`
- `Codex, muestra la estrategia activa y sus límites para Liga MX y NFL.`
- `Codex, consulta mi cuenta y reconcilia sólo en modo lectura.`
- `Codex, diagnostica por qué no aparece este fixture o mercado: <detalle>.`

## Datos, predicciones y backtests

- `Codex, actualiza los datos de Liga MX y verifica su frescura.`
- `Codex, actualiza nflverse para NFL desde 2022 y verifica su frescura.`
- `Codex, escanea Liga MX durante las próximas 168 horas en modo observación.`
- `Codex, calcula Poisson para Liga MX en la fecha YYYY-MM-DD.`
- `Codex, escanea NFL durante las próximas 240 horas.`
- `Codex, corre el backtest de Liga MX y NFL con bankroll de 1000, compáralos y dime la ruta exacta de cada reporte.`
- `Codex, genera los reportes HTML de backtest de Liga MX y NFL y dime comando, datos, métricas y rutas.`
- `Codex, simula las decisiones de Liga MX para YYYY-MM-DD sin tocar la wallet.`
- `Codex, simula las decisiones NFL para YYYY-MM-DD sin tocar la wallet.`
- `Codex, revisa este resultado post-evento y explica modelo, riesgo y sizing: <id>.`

## Desarrollo y mantenimiento

- `Codex, instala todas las dependencias y ejecuta tests, lint y pip check.`
- `Codex, corrige este fallo manteniendo el flujo unidireccional: <fallo>.`
- `Codex, genera el reporte editorial de YYYY-MM-DD sin publicarlo.`
- `Codex, revisa si una estrategia merece seguir draft; no cambies su estado.`

## Acciones que cambian dinero o estado

Estos pedidos requieren alcance concreto, revisión de gates y confirmación humana. No
se infieren desde “ayuda”, un análisis, un backtest ni un estado `AUTO`.

- `Codex, prepara para revisión una apuesta manual NFL de <stake> en <mercado>, sin ejecutarla.`
- `Codex, aprueba la decisión <key> por <stake>; muéstrame precio y pérdida máxima antes.`
- `Codex, cancela la orden <order_id>; verifica primero su estado.`
- `Codex, ejecuta NFL live para YYYY-MM-DD.`

Liga MX está en `draft`: sólo permite observación/dry-run. NFL está `approved`, pero
continúa en dry-run salvo una orden live explícita que supere todos los controles de
`EXECUTION_GOLIVE.md`.
