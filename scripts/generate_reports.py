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


def generate(*, as_of: date, bankroll: float) -> list[Path]:
    paths: list[Path] = []
    horizons = [data_horizon(tournament_id, as_of) for tournament_id in TOURNAMENTS]

    predictions = []
    for tournament_id in TOURNAMENTS:
        fixture_date = next_fixture_date(tournament_id, as_of)
        if fixture_date is None:
            continue
        predictions.append(
            daily_suggestions.compute(
                fixture_date,
                tournament_id,
                bankroll=bankroll,
                source_name="polymarket",
                allow_draft=True,
            )
        )
    paths.append(
        save_report(
            "_system",
            build_next_predictions_html(predictions, as_of=as_of.isoformat()),
            suffix="next-predictions",
            ext="html",
            date=as_of.isoformat(),
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
            "_system",
            build_backtest_to_date_html(report_data),
            suffix="backtest-to-date",
            ext="html",
            date=as_of.isoformat(),
        )
    )
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", help="fecha de corte YYYY-MM-DD; default: hoy UTC")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    args = parser.parse_args()
    for path in generate(as_of=_day(args.as_of), bankroll=args.bankroll):
        print(f"HTML: {path}")


if __name__ == "__main__":
    main()
