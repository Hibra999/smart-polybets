# TOURNAMENT: {Display Name}

tournament_id: {tournament_id}
sport: {football | american_football | basketball}
status: draft            # draft | active | completed | archived
start_date: {YYYY-MM-DD}
end_date: {YYYY-MM-DD}

## Descripción
[Qué torneo es, formato, número de equipos, fases.]

## Fuente de datos
- SQLite: `data/{tournament_id}/{tournament_id}.sqlite`
- Ver `data/{tournament_id}/DATA_SOURCES.md` para procedencia y actualización.

## Modelo
- Adapter: `adapters/{sport}/...`
- Modelo base: Elo (degrada a Elo si Bayes/TrueSkill no están wireados).

## Estrategias
| strategy_id | market_type | status |
|---|---|---|
| {strategy_id} | {market_type} | draft |
