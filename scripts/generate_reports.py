"""Genera predicciones próximas y backtest al día para Liga MX y NFL.

Sin argumentos usa la fecha UTC actual, detecta la próxima jornada de cada mercado y
elige automáticamente la última temporada con precios disponible para el backtest.
No consulta cuentas, no publica y no coloca órdenes.
"""

from __future__ import annotations

import argparse
import csv
import json
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

SNAPSHOT_FIELDS = (
    "snapshot_date", "snapshot_utc", "tournament_id", "fixture_id", "kickoff_utc",
    "home", "away", "pick_side", "condition_id", "token_id", "outcome", "source",
    "model_probability", "market_probability", "best_ask", "best_ask_size",
    "ask_levels_json", "volume_usdc", "liquidity_usdc", "fee_rate_bps", "tick_size",
    "min_order_size", "evaluated_stake", "expected_avg_price", "slippage_pct",
    "fee_usdc", "net_edge", "verdict", "action", "settlement",
)


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


def _settlement(tournament_id: str, fixture_id: str, pick_side: str) -> str:
    fixture = _reader(tournament_id).query_one(
        "SELECT status,home_team_id,away_team_id,winner_team_id FROM fixture WHERE id=?",
        (fixture_id,),
    )
    if not fixture or fixture["status"] != "finished" or pick_side not in {"HOME_WIN", "AWAY_WIN"}:
        return ""
    picked = fixture["home_team_id"] if pick_side == "HOME_WIN" else fixture["away_team_id"]
    return "WON" if fixture["winner_team_id"] == picked else "LOST"


def write_market_snapshots(predictions: list[dict], root: Path, snapshot_date: date) -> list[Path]:
    """Upsert diario de la recomendación y reconcilia resultados ya finalizados."""
    paths = []
    for prediction in predictions:
        tournament_id = prediction["tournament_id"]
        path = root / tournament_id / "ingest" / "market_snapshots.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        records: dict[tuple[str, str, str], dict] = {}
        if path.exists():
            with path.open(encoding="utf-8", newline="") as source:
                for record in csv.DictReader(source):
                    key = (record["snapshot_date"], record["fixture_id"], record["pick_side"])
                    records[key] = record

        for record in records.values():
            record["settlement"] = _settlement(
                tournament_id, record["fixture_id"], record["pick_side"]
            )
        for row in prediction["rows"]:
            record = {
                "snapshot_date": snapshot_date.isoformat(),
                "snapshot_utc": prediction["generated_at"],
                "tournament_id": tournament_id,
                "fixture_id": row["fixture_id"],
                "kickoff_utc": row["kickoff"],
                "home": row["home"],
                "away": row["away"],
                "pick_side": row["pick_side"],
                "condition_id": row.get("condition_id"),
                "token_id": row.get("token_id"),
                "outcome": row.get("outcome"),
                "source": prediction["source"],
                "model_probability": row.get("model_prob"),
                "market_probability": row.get("market_prob"),
                "best_ask": row.get("best_ask"),
                "best_ask_size": row.get("best_ask_size"),
                "ask_levels_json": json.dumps(row.get("top_asks") or [], separators=(",", ":")),
                "volume_usdc": row.get("volume_usdc"),
                "liquidity_usdc": row.get("liquidity_usdc"),
                "fee_rate_bps": row.get("base_fee_bps"),
                "tick_size": row.get("tick_size"),
                "min_order_size": row.get("min_order_size"),
                "evaluated_stake": row.get("evaluated_stake"),
                "expected_avg_price": row.get("expected_avg_price"),
                "slippage_pct": row.get("slippage_pct"),
                "fee_usdc": row.get("fee_usdc"),
                "net_edge": row.get("net_edge"),
                "verdict": row.get("verdict"),
                "action": row.get("action"),
                "settlement": _settlement(tournament_id, row["fixture_id"], row["pick_side"]),
            }
            records[(record["snapshot_date"], record["fixture_id"], record["pick_side"])] = record

        with path.open("w", encoding="utf-8", newline="") as destination:
            writer = csv.DictWriter(destination, fieldnames=SNAPSHOT_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(
                records[key] for key in sorted(records, key=lambda item: (item[0], item[1], item[2]))
            )
        paths.append(path)
    return paths


def generate(
    *,
    as_of: date,
    bankroll: float,
    output_dir: Path | None = None,
    snapshot_root: Path | None = None,
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
    if snapshot_root is not None:
        paths.extend(write_market_snapshots(predictions, snapshot_root, as_of))
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
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        help="guardar snapshots públicos diarios por torneo (requiere --live)",
    )
    args = parser.parse_args()
    if args.snapshot_dir is not None and not args.live:
        parser.error("--snapshot-dir requiere --live")
    for path in generate(
        as_of=_day(args.as_of),
        bankroll=args.bankroll,
        output_dir=args.publish_dir,
        snapshot_root=args.snapshot_dir,
        live=args.live,
    ):
        print(f"{'HTML' if path.suffix == '.html' else 'SNAPSHOT'}: {path}")


if __name__ == "__main__":
    main()
