# Hallazgo: datos desactualizados al recomendar — octavos sin ingestar + 4 partidos-hueco

**Fecha:** 2026-07-09 (PDC) · **Área:** `data/`, `venue/matching`, `scripts/update_results.py`,
`scripts/sync_upcoming_fixtures.py`, protocolo de sesión
**Síntoma:** el CIO preguntó si las recomendaciones usaban datos frescos. Auditoría: **no** —
el último resultado ingestado era del 2026-07-03. Las 3 apuestas de totales del día
(ver `2026-07-09-totals-live-sdk-tick.md`) se colocaron con modelos que no habían visto
**ninguno de los 8 octavos** (jugados 07-04 → 07-07).

## Contexto clave: los modelos reproducen la DB en runtime

`wc_pipeline` (Elo/Bayes/TrueSkill) y el Poisson **re-reproducen los fixtures `finished` en
orden cronológico en cada corrida**, partiendo del seed estático `team.elo_rating`. No hay
caché de ratings → **la frescura del modelo ES la frescura de la tabla `fixture`**. Arreglar
la DB arregla los modelos sin re-migrar nada.

## Gap 1 — Octavos sin finalizar (staleness operativo)

Los 8 octavos estaban jugados pero `scheduled`. `update_results.py --apply` los recuperó
al instante desde los mercados resueltos de PM. **Causa raíz: no había regla operativa de
refrescar datos antes de sugerir/apostar.** Fix: paso 5 del Protocolo de sesión (CLAUDE.md).

## Gap 2 — Irán: alias de canon faltante (`IR Iran`)

`wc_86` (Belgium–Iran, 06-21) y `wc_113` (Egypt–Iran, 06-26) llevaban semanas sin resultado.
Polymarket nombra al equipo **"IR Iran"** (nombre FIFA): `canon('IR Iran') = 'iriran'` ≠
`'iran'` → `update_results` nunca matcheaba el evento (los More Markets SÍ existían).
**Fix:** alias `"ir iran"/"iriran" → "iran"` en `venue/matching.py::ALIASES` (tests OK).
Mismo patrón que `curaao→curacao` / `trkiye→turkiye`.

## Gap 3 — Placeholders huérfanos: el sync solo ve mercados abiertos

`wc_121` (slot R32, "jugado" 06-28) y `wc_144` (slot R16, 07-07) seguían con placeholders
de bracket. Causa: `sync_upcoming_fixtures.py` mapea contra `match_events(closed=False)` —
si el partido se juega (mercado cierra) **entre dos corridas del sync**, el slot queda
huérfano y `update_results` tampoco puede finalizarlo (matchea por equipos).

**Identificación de los partidos reales** (pares de equipos cerrados en PM sin fixture en DB):
- `wc_121` = **South Africa vs. Canada** (R32, 06-28 19:00 UTC)
- `wc_144` = **Canada vs. Morocco** (R16, 07-04 17:00 UTC) — el octavo "fantasma" de Marruecos

Escritos a mano (backup `fifa_world_cup_2026.sqlite.bak-20260709T211148`, update condicionado
al placeholder → idempotente) y finalizados vía `update_results.py --apply`:

| Fixture | Resultado |
|---|---|
| wc_86 | Belgium 0-0 Iran |
| wc_113 | Egypt 1-1 Iran |
| wc_121 | South Africa 0-1 Canada |
| wc_144 | Canada 0-3 Morocco |

**Prevención:** correr el sync a diario durante eliminatorias (los mercados knockout viven
pocos días). Posible mejora futura: que el sync también consulte `closed=True` para
placeholders con kickoff pasado.

## Impacto en las apuestas colocadas (antes/después, mismo mercado)

| Apuesta | Poisson stale | Poisson completo | Mercado | Edge |
|---|---|---|---|---|
| Arg–Sui Over 2.5 | 60.8% | **58.4%** | 41.6% | +19.2 → **+16.8** |
| Nor–Ing Over 2.5 | 71.8% | **73.5%** | 55.4% | +16.4 → **+18.1** |
| Spa–Bel Under 2.5 | 55.3% | **62.1%** | 45.9% | +9.4 → **+16.2** |

Las 3 tesis sobreviven (2 se fortalecen; el 0-0 de Suiza le quita algo a la de Argentina).
Hubo suerte: la dirección no cambió — pero **el proceso estuvo mal** y de ahí la regla nueva.

## Estado final verificado (2026-07-09 ~16:15 PDC)

96 fixtures `finished`; único kickoff pasado en `scheduled` = `wc_145` France–Morocco
(**en juego** en ese momento — correcto). QFs `wc_146-148` sincronizados con equipos reales.
