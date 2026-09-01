"""Genera predicciones próximas y backtest al día para Liga MX y NFL.

Sin argumentos usa la fecha UTC actual, detecta la próxima jornada de cada mercado y
elige automáticamente la última temporada con precios disponible para el backtest.
No consulta cuentas, no publica y no coloca órdenes.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.workflows import daily_suggestions
from agent.workflows.pipeline_backtest import run as run_backtest
from core.exceptions import AgentError
from core.utils import utcnow
from editorial.functions import (
    build_backtest_to_date_html,
    build_next_predictions_html,
    save_report,
)
from editorial.functions.report_builder import REPORTS_ROOT
from tournaments.registry import TOURNAMENTS, get_adapter, get_config


def _day(value: str | None) -> date:
    return date.fromisoformat(value) if value else utcnow().date()


def _reader(tournament_id: str):
    reader = getattr(get_adapter(tournament_id), "reader", None)
    if reader is None:
        raise ValueError(f"El adapter de {tournament_id} no expone un reader")
    return reader


def next_fixture_date(tournament_id: str, as_of: date) -> str | None:
    row = _reader(tournament_id).query_one(
        "SELECT substr(kickoff_utc,1,10) AS fixture_date FROM fixture "
        "WHERE status='scheduled' AND datetime(kickoff_utc) >= datetime(?) "
        "ORDER BY datetime(kickoff_utc) LIMIT 1",
        (datetime.combine(as_of, time.min, tzinfo=UTC).isoformat(),),
    )
    return row["fixture_date"] if row else None


def data_horizon(tournament_id: str, as_of: date) -> dict:
    reader = _reader(tournament_id)
    config = get_config(tournament_id)
    cutoff = datetime.combine(as_of, time.max, tzinfo=UTC).isoformat()
    row = reader.query_one(
        "SELECT count(*) AS finished_to_date, max(kickoff_utc) AS latest_finished_utc "
        "FROM fixture WHERE status='finished' AND datetime(kickoff_utc) >= datetime(?) "
        "AND datetime(kickoff_utc) <= datetime(?)",
        (config.start_date, cutoff),
    ) or {"finished_to_date": 0, "latest_finished_utc": None}
    next_row = reader.query_one(
        "SELECT min(kickoff_utc) AS next_scheduled_utc FROM fixture "
        "WHERE status='scheduled' AND datetime(kickoff_utc) >= datetime(?)",
        (datetime.combine(as_of, time.min, tzinfo=UTC).isoformat(),),
    )
    return {
        "tournament_id": tournament_id,
        "display_name": config.display_name,
        "finished_to_date": int(row["finished_to_date"]),
        "latest_finished_utc": row["latest_finished_utc"],
        "next_scheduled_utc": next_row["next_scheduled_utc"] if next_row else None,
    }


def _report_location(output_dir: Path | None) -> tuple[Path | None, str]:
    """Convierte un directorio editorial explícito al contrato de ``save_report``."""
    if output_dir is None:
        return None, "_system"
    resolved = output_dir.resolve()
    reports_root = REPORTS_ROOT.resolve()
    if not resolved.is_relative_to(reports_root):
        raise ValueError(f"--publish-dir debe vivir bajo {reports_root}")
    return resolved.parent, resolved.name


def generate(
    *,
    as_of: date,
    bankroll: float,
    output_dir: Path | None = None,
    live: bool = False,
) -> list[Path]:
    paths: list[Path] = []
    horizons = [data_horizon(tournament_id, as_of) for tournament_id in TOURNAMENTS]
    report_root, report_bucket = _report_location(output_dir)

    predictions = []
    for tournament_id in TOURNAMENTS:
        fixture_date = next_fixture_date(tournament_id, as_of)
        if fixture_date is None:
            continue
        market_source = None
        source_name = "polymarket"
        if live:
            from research.functions import PolymarketLiveSource

            tag_id = get_config(tournament_id).polymarket_tag_id
            if tag_id is None:
                raise ValueError(f"{tournament_id} no tiene polymarket_tag_id")
            market_source = PolymarketLiveSource(tag_id=tag_id)
            source_name = "polymarket-live"
        predictions.append(
            daily_suggestions.compute(
                fixture_date,
                tournament_id,
                bankroll=bankroll,
                market_source=market_source,
                source_name=source_name,
                allow_draft=True,
            )
        )
    paths.append(
        save_report(
            report_bucket,
            build_next_predictions_html(predictions, as_of=as_of.isoformat()),
            suffix="next-predictions",
            ext="html",
            date=as_of.isoformat(),
            root=report_root,
        )
    )

    results = []
    for tournament_id in TOURNAMENTS:
        try:
            results.append(run_backtest(tournament_id, bankroll=bankroll, as_of=as_of.isoformat()))
        except (AgentError, FileNotFoundError, ValueError) as exc:
            results.append({"tournament_id": tournament_id, "available": False, "reason": str(exc)})
    report_data = {
        "as_of": as_of.isoformat(),
        "generated_at": utcnow().isoformat(),
        "bankroll": bankroll,
        "horizons": horizons,
        "results": results,
    }
    paths.append(
        save_report(
            report_bucket,
            build_backtest_to_date_html(report_data),
            suffix="backtest-to-date",
            ext="html",
            date=as_of.isoformat(),
            root=report_root,
        )
    )
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", help="fecha de corte YYYY-MM-DD; default: hoy UTC")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument(
        "--publish-dir",
        type=Path,
        help="directorio versionable bajo editorial/reports/ (ej. _system/published)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="leer mejores asks públicos de Polymarket; nunca envía órdenes",
    )
    args = parser.parse_args()
    for path in generate(
        as_of=_day(args.as_of),
        bankroll=args.bankroll,
        output_dir=args.publish_dir,
        live=args.live,
    ):
        print(f"HTML: {path}")


if __name__ == "__main__":
    main()
