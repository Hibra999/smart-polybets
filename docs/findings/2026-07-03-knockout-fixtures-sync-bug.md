# Hallazgo: los mercados de knockout no se ven (DB desincronizada del bracket real)

**Fecha:** 2026-07-03 (PDC) · **Área:** `data/` + `venue/` (`discovery`, `matching`) + `scripts/sync_upcoming_fixtures.py`
**Síntoma:** al pedir sugerencias/scan para partidos de knockout, salen como "sin cuota de mercado / SKIP",
como si Polymarket no tuviera mercado — cuando **sí lo tiene**. El sistema queda "ciego" a la ronda en curso.

## Verdad vs. DB (2026-07-03)

- **Polymarket (verdad, vía `venue.discovery.match_events`)** — fase de 32 en curso con mercado `Will X win` live:
  Colombia–Ghana (07-03 20:30 PDC), Canada–Morocco y Paraguay–France (07-04),
  Brazil–Norway y Mexico–England (07-05), Portugal–Spain (07-06)…
- **Cuenta live:** la única posición abierta/viva es **Colombia–Ghana** (cid `0xc4a26e…`, +2.55 uPnL).
  Las otras 7 posiciones ya están resueltas (sus `condition_id` ya no aparecen en eventos abiertos).
- **DB (`fifa_world_cup_2026.sqlite`):** el único fixture de la fase de 32 con equipos reales es `wc_136`
  (Colombia–Ghana). Los fixtures upcoming son placeholders:
  - `wc_137–144`: `round_of_32_N_winner` vs `round_of_32_M_winner` → estos son **octavos (R16)**.
  - `wc_145–148`: `round_of_16_N_winner` → **cuartos (QF)**.

## Causa raíz

1. **El regex de sync no matchea los placeholders actuales.** `scripts/sync_upcoming_fixtures.py`:
   ```python
   _GROUP_PH = re.compile(r"^group_[a-l]_(winner|2nd_place)$|^third_place_group", re.I)
   ```
   Solo reconoce placeholders **de grupo** (seeding de la fase de 32). Los pendientes hoy son
   `round_of_32_N_winner` / `round_of_16_N_winner`, que **no** matchean → el dry-run reporta
   `Placeholders pendientes: 0` y **sincroniza cero**. Por eso `matching` no puede mapear estos
   fixtures a los mercados live y las suggestions los tiran como "sin cuota / SKIP".

2. **A la DB le faltan los fixtures de la fase de 32 en curso** (salvo Colombia–Ghana). Los partidos
   reales (Canada–Morocco, Paraguay–France, …) no existen como fixtures con equipos. Los placeholders
   upcoming son de la ronda **siguiente** (octavos/QF).

3. **`phase` mal modelada:** no existe fila `r32` (la fase de 32, primer knockout del WC 2026), y **todos**
   los fixtures están tagueados `Group Stage` — incluidos los knockout. Ver `phase` table: solo
   `group_stage, r16, qf, sf, third_place, final`.

## Por qué NO basta con arreglar el regex (¡peligro!)

`sync_upcoming_fixtures.py` mapea `resolved[i] → pend[i]` **por orden de kickoff, 1:1**. Aun arreglando el
regex, el re-seed sería **incorrecto**:
- Los `resolved` (partidos live PM) son **fase de 32**; los `pend` (`round_of_32_*_winner`) son **octavos**.
  Se meterían partidos de fase de 32 en slots de octavos.
- Colombia–Ghana está en `resolved` (evento abierto) pero no en `pend` (ya tiene equipos) → el mapeo por
  orden se desalinea en 1 y duplica/corrompe.

## Fix recomendado (pendiente de aprobación del CIO)

1. Añadir fila `r32` a `phase` y **re-taguear** los knockouts (r32/r16/qf) en `fixture.phase_id`.
2. Crear/poblar los fixtures **de la fase de 32 en curso** con equipos reales + kickoff real desde
   `discovery.match_events` (no meterlos en slots de octavos).
3. Reescribir el mapeo del sync para que sea **por ronda y robusto**: filtrar `resolved` a la ronda cuyo
   kickoff coincide, excluir fixtures ya asignados (con equipos reales), y **validar conteos** antes de
   escribir (abortar si no cuadran, en vez de mapear por orden a ciegas).
4. Mantener backup del `.sqlite` (el script ya lo hace) y dry-run obligatorio.

## Cómo reproducir el diagnóstico

```bash
python scripts/sync_upcoming_fixtures.py                 # dry-run: "Placeholders pendientes: 0"
python scripts/scan_market.py --hours 120 --json        # solo devuelve Colombia–Ghana
python -c "from venue.discovery import match_events; [print(e.title, e.kickoff, e.has_winner_market) for e in match_events(closed=False)]"
python scripts/account.py --closed 300 --json           # posiciones live (verdad de apuestas)
```
