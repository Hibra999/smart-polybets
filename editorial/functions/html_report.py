"""HTML editorial para predicciones y backtests con el design system PEPA."""

from __future__ import annotations

import html
from typing import Any

_VERDICT = {
    "AUTO": ("#10B981", "Auto"),
    "REVIEW": ("#F59E0B", "Revisar"),
    "DISCARD": ("#EF4444", "Descartar"),
    "SKIP": ("#94A3B8", "Saltar"),
}
_CONF = {"HIGH": "Alta", "MEDIUM": "Media", "LOW": "Baja"}

_STYLE = """
  :root {
    --bg:#0F1117; --surface:#1A1D27; --surface-alt:#22262F; --border:#2D3340;
    --text:#E2E8F0; --muted:#94A3B8; --blue:#2563EB; --cyan:#22D3EE;
    --success:#10B981; --warning:#F59E0B; --danger:#EF4444;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
    font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif; line-height:1.6;
    -webkit-font-smoothing:antialiased; }
  .wrap { max-width:1040px; margin:0 auto; padding:48px 24px 64px; }
  .num { font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Consolas,monospace;
    font-variant-numeric:tabular-nums; }
  .muted { color:var(--muted); }
  header.top { border-bottom:1px solid var(--border); padding-bottom:24px; margin-bottom:32px; }
  .eyebrow { font-size:.75rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase;
    color:var(--cyan); }
  h1 { font-size:2.25rem; line-height:1.2; font-weight:700; letter-spacing:-.015em;
    margin:.25rem 0 .5rem; text-wrap:balance; }
  h2 { font-size:1.25rem; line-height:1.3; margin:36px 0 12px; text-wrap:balance; }
  .meta { color:var(--muted); font-size:.875rem; }
  .meta b { color:var(--text); font-weight:600; }
  .summary { margin-top:16px; max-width:72ch; font-size:.9375rem; text-wrap:pretty; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(360px,1fr));
    gap:16px; margin-top:8px; }
  .card, .report-block { background:var(--surface); border:1px solid var(--border);
    border-radius:12px; padding:20px; }
  .card-h, .section-h { display:flex; align-items:flex-start; justify-content:space-between;
    gap:12px; }
  .match { font-size:1.125rem; font-weight:600; }
  .vs { color:var(--muted); font-weight:400; font-size:.875rem; }
  .badge { display:inline-flex; align-items:center; font-size:.7rem; font-weight:600;
    letter-spacing:.06em; text-transform:uppercase; border:1px solid;
    border-radius:9999px; padding:4px 12px; white-space:nowrap; }
  .badges, .models, .targets { display:flex; flex-wrap:wrap; gap:6px; align-items:center; }
  .kick, .source, .reason { color:var(--muted); font-size:.8125rem; }
  .kick { margin:8px 0 16px; }
  .reason { margin-top:12px; }
  .grid { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:8px; }
  .cell, .metric { display:flex; flex-direction:column; gap:2px; min-width:0; }
  .k { font-size:.7rem; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
  .val { font-weight:600; overflow-wrap:anywhere; }
  .models { margin-top:14px; border-top:1px solid var(--border); padding-top:12px; }
  details.execution { margin-top:14px; border-top:1px solid var(--border); padding-top:12px; }
  details.execution summary { cursor:pointer; color:var(--cyan); font-size:.8125rem; }
  .contract { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px 16px;
    margin-top:10px; font-size:.75rem; }
  .contract .wide { grid-column:1/-1; overflow-wrap:anywhere; }
  .chip { font-size:.75rem; color:var(--muted); background:var(--surface-alt);
    border-radius:8px; padding:3px 10px; }
  .chip b { color:var(--text); }
  .consensus { margin-left:auto; color:var(--muted); font-size:.75rem; }
  .metrics { display:grid; grid-template-columns:repeat(auto-fit,minmax(125px,1fr));
    gap:1px; margin:16px 0; background:var(--border); border-radius:8px; overflow:hidden; }
  .metric { background:var(--surface-alt); padding:12px; }
  .metric strong { font-size:1.05rem; }
  .target { font-size:.75rem; border:1px solid var(--border); border-radius:8px; padding:4px 10px; }
  .target.ok { color:var(--success); border-color:#10B98155; }
  .target.fail { color:var(--danger); border-color:#EF444455; }
  .equity { margin:16px 0 8px; background:var(--bg); border-radius:8px; padding:8px; }
  .equity svg { display:block; width:100%; height:auto; }
  .table-wrap { overflow-x:auto; margin-top:16px; }
  table { width:100%; border-collapse:collapse; font-size:.8125rem; }
  th, td { padding:9px 10px; border-bottom:1px solid var(--border); text-align:left; }
  th { color:var(--muted); font-size:.7rem; letter-spacing:.04em; text-transform:uppercase; }
  td:nth-last-child(-n+3), th:nth-last-child(-n+3) { text-align:right; }
  footer { margin-top:40px; color:var(--muted); font-size:.8125rem;
    border-top:1px solid var(--border); padding-top:20px; }
  @media (max-width:620px) {
    .wrap { padding:28px 16px 40px; }
    h1 { font-size:1.75rem; }
    .cards { grid-template-columns:1fr; }
    .grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
    .card-h, .section-h { flex-direction:column; }
    .consensus { margin-left:0; width:100%; }
  }
  @media print {
    :root { --bg:#FFFFFF; --surface:#FFFFFF; --surface-alt:#F3F4F6; --border:#CBD5E1;
      --text:#111827; --muted:#475569; }
    .wrap { max-width:none; padding:16px; }
  }
"""


def _pct(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "n/d"


def _edge_html(edge: float | None) -> str:
    if edge is None:
        return '<span class="num muted">n/d</span>'
    color = "var(--cyan)" if edge > 0 else "var(--muted)"
    return f'<span class="num" style="color:{color}">{edge:+.1%}</span>'


def _contract_details(row: dict[str, Any]) -> str:
    if not row.get("token_id"):
        return ""
    asks = ", ".join(
        f"{price:.4f} × {size:.2f} shares" for price, size in row.get("top_asks", [])
    ) or "n/d"
    rules = html.escape(str(row.get("rules") or "n/d"))
    execution_reason = html.escape(str(row.get("execution_reason") or "cotización completa"))
    fields = [
        ("Condition", row.get("condition_id")),
        ("Token", row.get("token_id")),
        ("Pregunta", row.get("question") or "n/d"),
        ("Outcome", row.get("outcome") or "n/d"),
        ("Best ask", row.get("best_ask")),
        ("Ask size", row.get("best_ask_size")),
        ("Top asks", asks),
        ("Volumen USDC", row.get("volume_usdc")),
        ("Liquidez USDC", row.get("liquidity_usdc")),
        ("Tick", row.get("tick_size")),
        ("Orden mínima", row.get("min_order_size")),
        ("Base fee bps", row.get("base_fee_bps")),
        ("Slippage", _pct(row.get("slippage_pct"))),
        ("Precio promedio", row.get("expected_avg_price")),
        ("Fee USDC", row.get("fee_usdc")),
        ("Edge neto", _pct(row.get("net_edge"))),
        ("Muestra", row.get("sample_size")),
        ("Modelo", row.get("model_version")),
    ]
    cells = "".join(
        ('<div class="cell wide">' if label in {"Condition", "Token", "Pregunta", "Top asks"}
         else '<div class="cell">')
        + f'<span class="k">{html.escape(label)}</span>'
        + f'<span class="num">{html.escape(str(value if value is not None else "n/d"))}</span></div>'
        for label, value in fields
    )
    return f"""
        <details class="execution">
          <summary>Contrato y ejecución pública</summary>
          <div class="contract">{cells}
            <div class="cell wide"><span class="k">Reglas</span><span>{rules}</span></div>
            <div class="cell wide"><span class="k">Decisión de ejecución</span>
              <span>{execution_reason}</span></div>
          </div>
        </details>"""


def _document(
    *,
    title: str,
    eyebrow: str,
    heading: str,
    meta: str,
    summary: str,
    body: str,
    footer: str,
) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark light">
<title>{html.escape(title)}</title>
<style>{_STYLE}</style>
</head>
<body>
  <main class="wrap">
    <header class="top">
      <div class="eyebrow">{html.escape(eyebrow)}</div>
      <h1>{html.escape(heading)}</h1>
      <div class="meta">{meta}</div>
      <div class="summary">{summary}</div>
    </header>
    {body}
    <footer>{footer}</footer>
  </main>
</body>
</html>"""


def _model_chips(row: dict[str, Any]) -> str:
    values = []
    chips = []
    for name in ("elo", "bayes", "trueskill", "poisson", "dixon_coles"):
        value = row.get(name)
        if value is not None:
            values.append(float(value))
            chips.append(f'<span class="chip">{name} <b class="num">{_pct(value)}</b></span>')
    if row.get("poisson_draw") is not None:
        chips.append(
            '<span class="chip">empate Poisson '
            f'<b class="num">{_pct(row["poisson_draw"])}</b></span>'
        )
    if len(values) >= 2:
        spread = max(values) - min(values)
        label = (
            "consenso compacto"
            if spread <= 0.08
            else ("dispersión media" if spread <= 0.18 else "modelos en desacuerdo")
        )
        chips.append(
            f'<span class="consensus">{label} · rango <b class="num">{spread:.1%}</b></span>'
        )
    return "".join(chips)


def _prediction_card(row: dict[str, Any]) -> str:
    verdict = row.get("verdict", "SKIP")
    color, label = _VERDICT.get(verdict, _VERDICT["SKIP"])
    home, away = html.escape(row["home"]), html.escape(row["away"])
    pick = html.escape(str(row.get("pick_team", "")))
    confidence = _CONF.get(row.get("confidence", ""), row.get("confidence", ""))
    kickoff = html.escape(row.get("kickoff", "")[11:16])
    stake = row.get("stake") or 0.0
    stake_html = (
        f'<span class="num">{stake:.2f} USDC</span>'
        if stake > 0
        else '<span class="num muted">sin apuesta</span>'
    )
    action = html.escape(str(row.get("action", "NO_TRADE")))
    reason = html.escape(str(row.get("reason", "")))
    reason_html = f'<div class="reason">Motivo: {reason}</div>' if reason else ""
    return f"""
      <article class="card" aria-label="Predicción {home} contra {away}">
        <header class="card-h">
          <div class="match">{home} <span class="vs">vs</span> {away}</div>
          <span class="badge" style="color:{color};border-color:{color}55">{label}</span>
        </header>
        <div class="kick">Kickoff {kickoff} UTC, fase {html.escape(row.get("phase", ""))},
          confianza {html.escape(str(confidence))}</div>
        <div class="grid">
          <div class="cell"><span class="k">Pick</span><span class="val">{pick}</span></div>
          <div class="cell"><span class="k">Modelo</span><span class="num">{_pct(row.get("model_prob"))}</span></div>
          <div class="cell"><span class="k">Mercado</span><span class="num">{_pct(row.get("market_prob"))}</span></div>
          <div class="cell"><span class="k">Edge</span>{_edge_html(row.get("edge"))}</div>
          <div class="cell"><span class="k">Acción</span><span class="num">{action}</span>
            {stake_html}</div>
        </div>
        <div class="models">{_model_chips(row)}</div>
        {reason_html}
        {_contract_details(row)}
      </article>"""


def build_daily_html(data: dict[str, Any]) -> str:
    """Renderiza las predicciones de la próxima fecha de un torneo."""
    rows = data.get("rows", [])
    counts = {key: 0 for key in _VERDICT}
    for row in rows:
        key = row.get("verdict", "SKIP")
        counts[key] = counts.get(key, 0) + 1
    cards = "".join(_prediction_card(row) for row in rows)
    body = (
        f'<section class="cards">{cards}</section>'
        if cards
        else '<p class="muted">Sin partidos programados.</p>'
    )
    date = str(data.get("date", ""))
    tournament = str(data.get("tournament_name", data.get("tournament_id", "")))
    strategy = html.escape(str(data.get("strategy", "")))
    criterion = html.escape(str(data.get("side_criterion", "")))
    source = html.escape(str(data.get("source", "")))
    summary = (
        f"<b>{counts['AUTO']}</b> auto, <b>{counts['REVIEW']}</b> a revisar, "
        f"<b>{counts['DISCARD']}</b> descartadas y <b>{counts['SKIP']}</b> saltadas. "
        "Una predicción sin cuota sigue siendo una lectura de modelo, no una apuesta."
    )
    models = (
        "Elo, Bayes, TrueSkill, Poisson y Dixon-Coles"
        if any(row.get("poisson") is not None for row in rows)
        else "TrueSkill"
    )
    return _document(
        title=f"Predicciones {tournament} {date}",
        eyebrow=f"Sports Quant Trading, {tournament}",
        heading=f"Próximos partidos, {date}",
        meta=(
            f"Estrategia <b>{strategy}</b> ({criterion}, Kelly x{data.get('kelly_fraction')}), "
            f"cuotas <b>{source}</b>"
        ),
        summary=summary,
        body=body,
        footer=(
            f"Generado {html.escape(str(data.get('generated_at', '')))}. "
            f"Modelos visibles: {models}. No es consejo financiero; no se enviaron órdenes."
        ),
    )


def build_next_predictions_html(reports: list[dict[str, Any]], *, as_of: str) -> str:
    """Renderiza en un solo panel la próxima fecha de Liga MX y NFL."""
    sections = []
    total_matches = 0
    for data in reports:
        rows = data.get("rows", [])
        total_matches += len(rows)
        tournament = html.escape(str(data.get("tournament_name", data.get("tournament_id", ""))))
        cards = "".join(_prediction_card(row) for row in rows)
        sections.append(
            f"""
            <section aria-labelledby="{html.escape(str(data.get("tournament_id", "")))}-title">
              <header class="section-h">
                <div>
                  <h2 id="{html.escape(str(data.get("tournament_id", "")))}-title">{tournament}</h2>
                  <div class="source">Próxima fecha <b class="num">{html.escape(str(data.get("date", "")))}</b> ·
                    estrategia {html.escape(str(data.get("strategy", "")))} · cuotas
                    {html.escape(str(data.get("source", "")))}</div>
                </div>
                <span class="badge" style="color:var(--cyan);border-color:#22D3EE55">
                  {len(rows)} partido{"s" if len(rows) != 1 else ""}</span>
              </header>
              <div class="cards">{cards}</div>
            </section>"""
        )
    return _document(
        title=f"Próximos partidos hasta {as_of}",
        eyebrow="Sports Quant Trading, Liga MX + NFL",
        heading="Próximos partidos",
        meta=f'Corte automático <b class="num">{html.escape(as_of)}</b> · sólo lectura',
        summary=(
            f"<b>{total_matches}</b> partidos en la próxima fecha disponible. "
            "Elo, Bayes, TrueSkill, Poisson y Dixon-Coles se muestran por separado; "
            "sin costes públicos completos no se muestra SIMULATED_BUY."
        ),
        body="".join(sections) or '<p class="muted">Sin partidos programados.</p>',
        footer=(
            "Datos locales SQLite y cotizaciones públicas de Polymarket. Panel informativo: "
            "toda compra indicada es simulada; no se enviaron órdenes."
        ),
    )


def _sparkline(result: dict[str, Any]) -> str:
    perf = result["performance"]
    values = [float(perf["bankroll_initial"])] + [
        float(bet["bankroll"]) for bet in result.get("bets", [])
    ]
    if len(values) < 2:
        return '<p class="muted">Sin apuestas AUTO para trazar bankroll.</p>'
    width, height, pad = 720, 170, 14
    low, high = min(values), max(values)
    span = high - low or 1.0
    points = []
    for index, value in enumerate(values):
        x = pad + index * (width - 2 * pad) / (len(values) - 1)
        y = height - pad - (value - low) * (height - 2 * pad) / span
        points.append(f"{x:.1f},{y:.1f}")
    color = "var(--success)" if values[-1] >= values[0] else "var(--danger)"
    return f"""
      <div class="equity">
        <svg viewBox="0 0 {width} {height}" role="img"
          aria-label="Bankroll de {values[0]:.2f} a {values[-1]:.2f} USDC">
          <line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}"
            stroke="var(--border)"/>
          <polyline points="{" ".join(points)}" fill="none" stroke="{color}"
            stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="{points[-1].split(",")[0]}" cy="{points[-1].split(",")[1]}" r="4"
            fill="{color}"/>
        </svg>
      </div>"""


def _recent_bets(result: dict[str, Any]) -> str:
    rows = []
    for bet in result.get("bets", [])[-8:]:
        pnl = float(bet["pnl"])
        pnl_color = "var(--success)" if pnl >= 0 else "var(--danger)"
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(bet.get('kickoff_utc', ''))[:10])}</td>"
            f"<td>{html.escape(str(bet.get('match', bet['event_id'])))}</td>"
            f"<td>{html.escape(str(bet['pick']))}</td>"
            f'<td class="num">{float(bet["edge"]):+.1%}</td>'
            f'<td class="num">{float(bet["stake"]):.2f}</td>'
            f'<td class="num" style="color:{pnl_color}">{pnl:+.2f}</td>'
            "</tr>"
        )
    if not rows:
        return ""
    return f"""
      <div class="table-wrap">
        <table>
          <thead><tr><th>Fecha</th><th>Partido</th><th>Pick</th><th>Edge</th>
            <th>Stake</th><th>PnL</th></tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </div>"""


def _backtest_section(result: dict[str, Any], horizon: dict[str, Any]) -> str:
    if result.get("available") is False:
        return f"""
          <section class="report-block">
            <h2>{html.escape(horizon["display_name"])}</h2>
            <p class="muted">No disponible: {html.escape(result["reason"])}</p>
          </section>"""
    perf = result["performance"]
    coverage = result["coverage"]
    met = result["targets"]["met"]
    targets = "".join(
        f'<span class="target {"ok" if ok else "fail"}">{html.escape(name)}: '
        f"{'Cumple' if ok else 'Falla'}</span>"
        for name, ok in met.items()
    )
    roi_color = "var(--success)" if perf["roi"] >= 0 else "var(--danger)"
    latest_finished = horizon.get("latest_finished_utc")
    latest_label = str(latest_finished)[:10] if latest_finished else "sin partidos"
    current_note = (
        f'Temporada actual: <b class="num">{horizon["finished_to_date"]}</b> finalizados '
        f'hasta hoy; último <b class="num">{html.escape(latest_label)}</b>.'
    )
    return f"""
      <section class="report-block">
        <header class="section-h">
          <div>
            <h2 style="margin:0">{html.escape(horizon["display_name"])}</h2>
            <div class="source">Temporada con precios: {html.escape(str(result["season"]))} ·
              muestra {coverage["with_price"]}/{coverage["games"]} · {current_note}</div>
          </div>
          <div class="targets">{targets}</div>
        </header>
        <div class="metrics">
          <div class="metric"><span class="k">Bankroll final</span>
            <strong class="num">${perf["bankroll_final"]:,.2f}</strong></div>
          <div class="metric"><span class="k">ROI</span>
            <strong class="num" style="color:{roi_color}">{perf["roi"]:+.1%}</strong></div>
          <div class="metric"><span class="k">Win rate</span>
            <strong class="num">{perf["win_rate"]:.1%}</strong></div>
          <div class="metric"><span class="k">Max drawdown</span>
            <strong class="num">{perf["max_drawdown"]:.1%}</strong></div>
          <div class="metric"><span class="k">Apuestas</span>
            <strong class="num">{perf["bets"]}</strong></div>
          <div class="metric"><span class="k">Decisiones</span>
            <strong class="num">{result["decisions"]["AUTO"]} AUTO</strong></div>
        </div>
        {_sparkline(result)}
        <div class="source">Fuente: {html.escape(result["price_source"])}. Corte del benchmark:
          {html.escape(str(result.get("latest_event_utc", "n/d"))[:10])}. Simulación walk-forward.</div>
        {_recent_bets(result)}
      </section>"""


def build_backtest_to_date_html(data: dict[str, Any]) -> str:
    """Renderiza un backtest cross-torneo con corte automático."""
    horizons = {item["tournament_id"]: item for item in data.get("horizons", [])}
    sections = "".join(
        _backtest_section(result, horizons[result["tournament_id"]])
        for result in data.get("results", [])
    )
    failures = sum(
        1
        for result in data.get("results", [])
        if result.get("available") is not False and not all(result["targets"]["met"].values())
    )
    as_of = str(data.get("as_of", ""))
    return _document(
        title=f"Backtest hasta {as_of}",
        eyebrow="Sports Quant Trading, Liga MX + NFL",
        heading=f"Backtest hasta {as_of}",
        meta=(
            f'Bankroll inicial <b class="num">${float(data.get("bankroll", 0)):,.2f}</b> · '
            "última temporada con precios disponible por mercado"
        ),
        summary=(
            f"<b>{failures}</b> mercado(s) no cumplen todos sus targets. El corte es automático "
            "y nunca incluye partidos posteriores a la fecha del reporte."
        ),
        body=f'<div style="display:grid;gap:20px">{sections}</div>',
        footer=(
            f"Generado {html.escape(str(data.get('generated_at', '')))}. "
            "Resultados simulados; no representan órdenes reales ni garantizan rendimiento futuro."
        ),
    )
