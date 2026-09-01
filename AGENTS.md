# Reglas del repositorio para Codex

Este repositorio se opera exclusivamente con Codex. Al iniciar una sesión, lee
`INIT.md`; si el usuario pide ayuda, lee también `docs/PROMPTS.md`.

## Alcance

Sólo existen dos mercados soportados:

- `liga_mx_2026`: Liga MX Apertura 2026, estrategia `draft`; observación y dry-run.
- `nfl_2026`: NFL 2026, estrategia aprobada; dry-run salvo autorización live explícita.

No agregues mercados fuera de esos dos IDs. El flujo único es
`Research → Risk → Optimization → Execution → Portfolio → Editorial`.

## Ayuda

Cuando el usuario escriba `Codex, help`, `help`, `ayuda`, “qué puedo pedir” o solicite
los prompts disponibles, usa `$pepa-help`: muestra el catálogo de `docs/PROMPTS.md` y
no ejecutes ninguno de sus ejemplos.

## Organización y límites

La lógica pura vive en `*/functions/`, los contratos Pydantic en `*/schemas/`, los
comandos en `scripts/`, los datos en `data/` y las estrategias en `tournaments/`.
Todo acceso a Polymarket pasa por `venue/`; ningún script o área llama al SDK directo.
Respeta los `SKILL.md` del área que toques y no inviertas dependencias entre etapas.

## Desarrollo

```bash
python3.11 -m venv .venv
.venv/bin/pip install --pre -e ".[dev,optimize,live,nfl]"
.venv/bin/pytest
.venv/bin/ruff check .
```

Usa Python 3.11, cuatro espacios, línea máxima de 100 caracteres y nombres estándar
de Python. Prefiere pruebas deterministas, SQLite en memoria y cero red en tests.

## Entrega y Git

Después de cada cambio solicitado: valida lo afectado, comprueba que no entren secretos,
SQLite ni estado local, crea un commit descriptivo y sube la rama actual a `origin`.
Al entregar, indica rama y SHA. Si el push falla, conserva el commit local y explica el
bloqueo; nunca fuerces ni reescribas historia sin autorización explícita.

Después de cada backtest indica siempre torneo, temporada, bankroll, fuente de precios,
métricas principales y ruta exacta del reporte. Si el comando sólo imprimió a terminal,
di expresamente que no guardó archivo y ofrece el generador HTML correspondiente.
El generador canónico es `scripts/generate_reports.py`: sin argumentos toma hoy UTC,
detecta las próximas fechas de Liga MX/NFL y actualiza los HTML bajo
`editorial/reports/`. `SessionStart` lo ejecuta automáticamente después de freshness.

## Seguridad

No versionar `.env`, llaves, respuestas autenticadas, SQLite generados ni estados de
cuenta. La ejecución es dry-run por defecto. No debilitar los gates acumulativos:
`--live`, `POLYMARKET_LIVE=1`, signer válido, kill-switch desactivado y confirmación
tipada. `REVIEW` siempre espera aprobación humana. Lee `EXECUTION_GOLIVE.md` antes de
tocar dinero o código de ejecución.
