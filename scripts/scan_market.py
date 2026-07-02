#!/usr/bin/env python
"""scan_market.py — entrypoint Polymarket-first (mercado → señal → edge).

Registra el provider de fútbol, consulta los fixtures próximos en el torneo
activo, obtiene precios live de Polymarket y calcula el edge modelo - mercado.
Read-only, dry-run. Demuestra el seam "sports as plugins":

    agregar un deporte = registrar un SignalProvider (sin cambiar el pipeline)

Uso:
    python scripts/scan_market.py                       # próximas 48h, WC 2026
    python scripts/scan_market.py --hours 72            # amplía ventana
    python scripts/scan_market.py --tournament fifa_world_cup_2026 --sport football
    python scripts/scan_market.py --json                # salida JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── sys.path (permite correr como script desde cualquier directorio) ─────────
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

# ── consola UTF-8 + env ANTES de cualquier import de negocio ─────────────────
from core.console import enable_utf8  # noqa: E402

enable_utf8()

from core.env import load_env  # noqa: E402

load_env(_REPO / ".env")

# ── tag IDs de Polymarket por torneo (fuente: research/functions/polymarket_live.py) ──
_TAG_IDS: dict[str, int] = {
    "fifa_world_cup_2026": 102232,
}

# ── lógica principal ──────────────────────────────────────────────────────────


def _pct(x) -> str:
    """Formatea un Decimal/float como porcentaje con 1 decimal."""
    try:
        return f"{float(x) * 100:5.1f}%"
    except (TypeError, ValueError):
        return "  n/d"


def _edge_str(edge) -> str:
    try:
        return f"{float(edge) * 100:+.1f}%"
    except (TypeError, ValueError):
        return " n/d"


def run(tournament_id: str, hours: int, sport: str, as_json: bool) -> int:
    """Escanea mercados y muestra oportunidades. Retorna el exit code."""
    from core.exceptions import AccountUnavailableError, NotFoundError
    from adapters.football.db_reader import FootballDBReader
    from signals.football import FootballSignalProvider
    from signals import registry
    from tournaments.registry import load_active_strategy
    from venue.gateway import PolymarketGateway

    # ── 1. Estrategia activa ──────────────────────────────────────────────────
    try:
        strategy = load_active_strategy(tournament_id)
    except NotFoundError as exc:
        print(f"[scan_market] Torneo no registrado: {exc}", file=sys.stderr)
        return 1

    if strategy is None:
        print(
            f"[scan_market] No hay estrategia aprobada para '{tournament_id}'. "
            "Aprobar una estrategia en STRATEGY.md antes de escanear.",
            file=sys.stderr,
        )
        return 1

    # ── 2. Registrar el provider de señal ────────────────────────────────────
    provider = FootballSignalProvider(tournament_id=tournament_id, strategy=strategy)
    registry.register(provider)

    # ── 3. Fixtures próximos ─────────────────────────────────────────────────
    try:
        db = FootballDBReader(tournament_id)
    except FileNotFoundError as exc:
        print(f"[scan_market] Base de datos no encontrada: {exc}", file=sys.stderr)
        return 1

    upcoming = db.get_upcoming_fixtures(hours_ahead=hours)
    if not upcoming:
        print(
            f"[scan_market] Sin fixtures programados en las próximas {hours}h "
            f"para '{tournament_id}'."
        )
        return 0

    # ── 4. Gateway (descubrimiento — read-only, sin auth) ────────────────────
    gateway = PolymarketGateway()
    tag_id = _TAG_IDS.get(tournament_id)

    # ── 5. Cabecera ──────────────────────────────────────────────────────────
    prov = registry.get(sport)
    if prov is None:
        print(
            f"[scan_market] No hay provider registrado para el deporte '{sport}'. "
            "Registrar un SignalProvider antes de escanear.",
            file=sys.stderr,
        )
        return 1

    if not as_json:
        print(
            f"\n=== scan_market · {tournament_id} · próximas {hours}h "
            f"· deporte={sport} ===\n"
        )
        header = (
            f"{'FIXTURE':<34} {'PICK':<10} {'MODELO':>8} {'MERCADO':>8} "
            f"{'EDGE':>7}  {'CONF':<8} {'N':>5}"
        )
        print(header)
        print("  " + "-" * (len(header) + 2))

    rows: list[dict] = []

    for fix in upcoming:
        fixture_id = str(fix["id"])
        # Resolver nombres de equipo via get_fixture (tiene el JOIN con team)
        details = db.get_fixture(fixture_id)
        if details is None:
            continue
        home = details["home_team_name"] or ""
        away = details["away_team_name"] or ""
        kickoff = fix.get("kickoff_utc", "")
        label = f"{home} vs {away}"

        # ── señal del modelo ──────────────────────────────────────────────
        try:
            sig = prov.signal(home, away, event_id=fixture_id)
        except Exception as exc:  # noqa: BLE001 — model errors no deben romper el scan
            _skip(label, f"error en modelo: {type(exc).__name__}: {exc}", as_json, rows)
            continue

        if sig is None:
            _skip(label, "sin señal (modelo no disponible para este fixture)", as_json, rows)
            continue

        # ── mercados de Polymarket ────────────────────────────────────────
        try:
            markets = gateway.find_match_markets(home, away, tag_ids=tag_id)
        except AccountUnavailableError as exc:
            msg = (
                f"Gateway de Polymarket no disponible: {exc}\n"
                "  Acción: verificar conexión a internet / instalar SDK:\n"
                "  pip install --pre polymarket-client"
            )
            print(f"\n[scan_market] {msg}")
            return 0
        except Exception as exc:  # noqa: BLE001
            msg = (
                f"Error al consultar Polymarket para {label}: "
                f"{type(exc).__name__}: {exc}"
            )
            _skip(label, msg, as_json, rows)
            continue

        # Buscar el mercado que coincide con el lado del modelo
        matched = next(
            (m for m in markets if m.model_outcome == sig.side), None
        )
        if matched is None:
            sides_found = [m.model_outcome for m in markets] or ["ninguno"]
            _skip(
                label,
                f"sin mercado para '{sig.side}' en Polymarket "
                f"(encontrados: {', '.join(sides_found)})",
                as_json,
                rows,
            )
            continue

        edge = sig.model_probability - matched.market_probability

        row = {
            "fixture": label,
            "kickoff_utc": kickoff,
            "side": sig.side,
            "model_prob": float(sig.model_probability),
            "market_prob": float(matched.market_probability),
            "edge": float(edge),
            "confidence": sig.model_confidence,
            "sample_size": sig.sample_size,
            "condition_id": matched.condition_id,
            "token_id": matched.token_id,
            "best_ask": float(matched.best_ask) if matched.best_ask is not None else None,
        }
        rows.append(row)

        if not as_json:
            print(
                f"{label:<34} {sig.side:<10} "
                f"{_pct(sig.model_probability):>8} {_pct(matched.market_probability):>8} "
                f"{_edge_str(edge):>7}  {sig.model_confidence:<8} {sig.sample_size:>5}"
            )

    if as_json:
        opportunities = [r for r in rows if "skip" not in r]
        print(json.dumps(opportunities, indent=2, ensure_ascii=False))
    else:
        opportunities = [r for r in rows if "skip" not in r]
        print()
        if opportunities:
            print(f"  {len(opportunities)} oportunidad(es) encontrada(s).")
        else:
            print("  Sin oportunidades (sin señal o sin mercado activo en Polymarket).")

    return 0


def _skip(label: str, reason: str, as_json: bool, rows: list) -> None:
    """Registra un fixture saltado con su razón."""
    if as_json:
        rows.append({"fixture": label, "skip": True, "reason": reason})
    else:
        print(f"  [skip] {label}: {reason}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Escanea mercados de Polymarket y calcula edge vs. modelo (dry-run)."
    )
    ap.add_argument(
        "--tournament", default="fifa_world_cup_2026",
        help="ID del torneo (default: fifa_world_cup_2026)"
    )
    ap.add_argument(
        "--hours", type=int, default=48,
        help="Ventana de fixtures en horas (default: 48)"
    )
    ap.add_argument(
        "--sport", default="football",
        help="Deporte / key del provider (default: football)"
    )
    ap.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Salida en formato JSON"
    )
    args = ap.parse_args()

    sys.exit(run(args.tournament, args.hours, args.sport, args.as_json))


if __name__ == "__main__":
    main()
