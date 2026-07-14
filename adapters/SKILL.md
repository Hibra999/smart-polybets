# SKILL: Adapters (Capa de Datos)

## ROL EN EL SISTEMA
Proveer acceso a los datos del torneo almacenados en SQLite.
Es la única capa que toca los archivos .sqlite — ninguna otra área
accede directamente a los datos crudos.

## CUÁNDO INVOCAR
- Research necesita datos del partido antes de calcular edge
- Se necesita verificar disponibilidad de jugadores (activa QR-002)
- Se requiere historial head-to-head para contexto cualitativo
- Claude necesita hacer un join entre torneos del mismo deporte

## CUÁNDO NO INVOCAR
- Para datos de Polymarket (eso es CLOB API vía research/)
- Para estado del portafolio (eso es portfolio/ vía LocalState)
- Para escribir resultados de trading (los adapters son read-only)

## READERS DISPONIBLES

| Clase | Deporte | Archivo |
|---|---|---|
| `FootballDBReader` | Fútbol asociación | `adapters/football/db_reader.py` |
| `AmericanFootballDBReader` | NFL | `adapters/american_football/db_reader.py` |
| `FootballCrossTournamentJoiner` | Cross-torneo fútbol | `adapters/football/cross_tournament_joiner.py` |

## ADAPTERS DE MODELO (producen MatchPrediction)

| Clase | Modelo | Estado |
|---|---|---|
| `FootballEloAdapter` | Elo 1X2 | implementado (modelo Elo real) |
| `FootballBayesAdapter` | Bayes jerárquico | loader legacy: degrada a Elo. Los modelos WC REALES (Elo+Bayes+TrueSkill migrados) viven en `wc_models.py`/`wc_pipeline.py` (+ Poisson en `wc_poisson.py`) y son los que usa `match_winner_wc_v1` |
| `FootballTrueSkillAdapter` | TrueSkill | loader legacy: degrada a Elo (ídem: el real está en `wc_trueskill.py`) |
| `AmericanFootballEloAdapter` | Elo binario NFL | implementado |

**Localía (2026-07-14)**: `EloSystem.home_adv` (puntos Elo; team_a = local en
`update_match`) y `PoissonGoalsModel(neutral=False)` se configuran POR TORNEO vía
`TournamentConfig.{home_adv_elo, neutral_venue}` en `tournaments/registry.py`
(Mundial: 0/neutral; Liga MX: 65 placeholder/con localía). Bayes y TrueSkill no
llevan localía (señal de fuerza relativa). Con Elo seed flat 1500, TrueSkill (μ=25)
y Bayes (0.5) arrancan uniformes por construcción — cold start coherente.

## INSTANCIACIÓN
```python
# Siempre pasar tournament_id explícito
reader = FootballDBReader(tournament_id="fifa_world_cup_2026")
fixture = reader.get_fixture("match_123")

# Para tests: inyectar una conexión sqlite3 (ej: :memory:)
reader = FootballDBReader("t", connection=conn)
```

## CONSTRAINTS
- NUNCA escribir en el SQLite desde esta capa (read-only)
- Si el archivo SQLite no existe → FileNotFoundError inmediato, no silencioso
- Si player_availability retorna jugadores con status != available →
  SIEMPRE incluir como qualitative_flag QR-002 en el RiskVerdict
- Los datos de player_availability son best-effort: pueden estar desactualizados

## ERRORES COMUNES
- Asumir que el fixture_id del SQLite es el mismo que el condition_id de Polymarket (NO lo son)
- Usar cross_tournament_joiner cuando solo hay un torneo (overhead innecesario)
- No verificar que el SQLite existe antes de instanciar el reader
