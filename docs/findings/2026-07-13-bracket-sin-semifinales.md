# 2026-07-13 — El bracket de la DB termina en cuartos: SF/3er puesto/final no existen

## Síntoma
Tras finalizar los 4 QF (`update_results.py --apply` OK), `sync_upcoming_fixtures.py` reportó
`2 partidos PM vs 0 placeholders` y `scan_market.py --hours 48` no encontró fixtures,
aunque Polymarket tenía abiertas las dos semifinales (France vs. Spain 07-14, England vs.
Argentina 07-15).

## Causa raíz
La DB se construyó con **100 fixtures** y el Mundial de 48 equipos tiene **104 partidos**
(72 grupos + 16 R32 + 8 R16 + 4 QF + 2 SF + 3er puesto + final). Los placeholders de bracket
solo cubren hasta cuartos (`wc_148`). Sin filas placeholder, `sync_upcoming_fixtures.py`
no tiene dónde escribir los cruces (mapea PM → placeholders existentes; no crea fixtures).

## Fix aplicado (2026-07-13)
Backup `fifa_world_cup_2026.sqlite.bak-sf-20260713` + inserción manual de:
- `wc_149` france vs spain, kickoff 2026-07-14T19:00:00+00:00, `scheduled`
- `wc_150` england vs argentina, kickoff 2026-07-15T19:00:00+00:00, `scheduled`

Convenciones copiadas de los QF: `phase_id='group_stage'` (así están todos los knockouts en
esta DB), `neutral_venue=1`, ids consecutivos. Kickoffs tomados de `venue.discovery.match_events()`.

## Pendiente
- **3er puesto y final** (`wc_151`, `wc_152`): habrá que insertarlos igual cuando PM los abra
  (después de las semis). Mismo procedimiento: backup → INSERT → `scan_market.py` para verificar.
- Nota: England y Argentina avanzaron por penales (1-1 a 90' en `wc_147`/`wc_148`;
  `winner_team_id` quedó NULL — el marcador de PM solo da el 90').

## Verificación del día
`scan_market.py --hours 48` ve ambas semis. Recordatorio de la regla 90': los edges del blend
(France +13.2%, Argentina +25.5%) son fantasma; el Poisson 1X2 da France 32.1% (mercado 40.4%
→ CARO) y Argentina 37.1% (mercado 31.4% → edge real modesto ~+5.7%).
