"""Reporte HTML de las sugerencias del día.

Sigue el design system de pypro.mx ("Editor at Night"): dark por defecto
(#0F1117), un único color de señal Operator Blue (#2563EB), acento cyan
(#22D3EE), Inter para texto y JetBrains Mono para números. Sin emojis-bullet,
sin em-dashes en el copy, sin gradientes.

Función pura: recibe el dict de daily_suggestions.compute() y devuelve HTML.
"""
from __future__ import annotations

import html
from typing import Any

# Colores funcionales por veredicto (tokens del design system).
_VERDICT = {
    "AUTO": ("#10B981", "Auto"),       # success
    "REVIEW": ("#F59E0B", "Revisar"),  # warning
    "DISCARD": ("#EF4444", "Descartar"),  # error
    "SKIP": ("#94A3B8", "Saltar"),     # muted
}
_CONF = {"HIGH": "Alta", "MEDIUM": "Media", "LOW": "Baja"}


def _pct(x: float | None) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/d"


def _edge_html(edge: float | None) -> str:
    if edge is None:
        return '<span class="num muted">n/d</span>'
    color = "#22D3EE" if edge > 0 else "#94A3B8"
    sign = "+" if edge >= 0 else ""
    return f'<span class="num" style="color:{color}">{sign}{edge * 100:.1f}%</span>'


def _card(row: dict[str, Any]) -> str:
    v = row.get("verdict", "SKIP")
    color, label = _VERDICT.get(v, _VERDICT["SKIP"])
    home, away = html.escape(row["home"]), html.escape(row["away"])
    pick = html.escape(str(row.get("pick_team", "")))
    conf = _CONF.get(row.get("confidence", ""), row.get("confidence", ""))
    kickoff = html.escape(row.get("kickoff", "")[11:16])  # HH:MM
    stake = row.get("stake") or 0.0
    stake_html = (f'<span class="num">{stake:.2f} USDC</span>'
                  if stake > 0 else '<span class="num muted">sin apuesta</span>')

    comp = []
    for name in ("elo", "bayes", "trueskill"):
        val = row.get(name)
        if val is not None:
            comp.append(f'<span class="chip">{name} <b class="num">{_pct(val)}</b></span>')
    comp_html = "".join(comp)

    yolo_badge = ('<span class="badge yolo">YOLO</span>'
                  if row.get("yolo") else "")
    note = row.get("cio_note")
    note_html = (f'<div class="cio"><span class="cio-k">Nota del CIO</span>'
                 f'<p>{html.escape(str(note))}</p></div>' if note else "")

    return f"""
      <article class="card{' card-yolo' if row.get('yolo') else ''}">
        <header class="card-h">
          <div class="match">{home} <span class="vs">vs</span> {away}</div>
          <div class="badges">{yolo_badge}<span class="badge" style="color:{color};border-color:{color}33;background:{color}14">{label}</span></div>
        </header>
        <div class="kick">Kickoff {kickoff} UTC, fase {html.escape(row.get('phase',''))}, confianza {conf}</div>
        <div class="grid">
          <div class="cell"><span class="k">Pick</span><span class="val">{pick}</span></div>
          <div class="cell"><span class="k">Modelo</span><span class="num">{_pct(row.get('model_prob'))}</span></div>
          <div class="cell"><span class="k">Mercado</span><span class="num">{_pct(row.get('market_prob'))}</span></div>
          <div class="cell"><span class="k">Edge</span>{_edge_html(row.get('edge'))}</div>
          <div class="cell"><span class="k">Sugerido</span>{stake_html}</div>
        </div>
        <div class="models">{comp_html}</div>
        {note_html}
      </article>"""


def build_daily_html(data: dict[str, Any]) -> str:
    rows = data.get("rows", [])
    counts = {k: 0 for k in _VERDICT}
    for r in rows:
        counts[r.get("verdict", "SKIP")] = counts.get(r.get("verdict", "SKIP"), 0) + 1
    cards = "".join(_card(r) for r in rows) or '<p class="muted">Sin partidos programados.</p>'
    date = html.escape(data.get("date", ""))
    strat = html.escape(str(data.get("strategy", "")))
    crit = html.escape(str(data.get("side_criterion", "")))
    kelly = data.get("kelly_fraction")
    src = html.escape(str(data.get("source", "")))
    tournament = html.escape(str(data.get("tournament_name", data.get("tournament_id", ""))))
    summary = (f'{counts["AUTO"]} auto, {counts["REVIEW"]} a revisar, '
               f'{counts["DISCARD"]} descartadas, {counts["SKIP"]} saltadas')

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sugerencias {tournament} {date}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#0F1117; --surface:#1A1D27; --surface-alt:#22262F; --border:#2D3340;
    --text:#E2E8F0; --muted:#94A3B8; --blue:#2563EB; --cyan:#22D3EE;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
    font-family:Inter,system-ui,sans-serif; line-height:1.6;
    -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:960px; margin:0 auto; padding:48px 24px 64px; }}
  .num {{ font-family:'JetBrains Mono',ui-monospace,monospace; }}
  .muted {{ color:var(--muted); }}
  header.top {{ border-bottom:1px solid var(--border); padding-bottom:24px; margin-bottom:32px; }}
  .eyebrow {{ font-size:.75rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase;
    color:var(--cyan); }}
  h1 {{ font-size:2.25rem; font-weight:700; letter-spacing:-.015em; margin:.25rem 0 .5rem; }}
  .meta {{ color:var(--muted); font-size:.875rem; }}
  .meta b {{ color:var(--text); font-weight:600; }}
  .summary {{ margin-top:16px; font-size:.9375rem; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(380px,1fr)); gap:16px; margin-top:8px; }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:20px; }}
  .card-h {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
  .match {{ font-size:1.125rem; font-weight:600; }}
  .vs {{ color:var(--muted); font-weight:400; font-size:.875rem; }}
  .badge {{ font-size:.7rem; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
    border:1px solid; border-radius:9999px; padding:4px 12px; white-space:nowrap; }}
  .badges {{ display:flex; gap:6px; align-items:center; }}
  .badge.yolo {{ color:#0F1117; background:var(--cyan); border-color:var(--cyan);
    font-weight:800; letter-spacing:.08em; }}
  .card-yolo {{ border-color:#22D3EE55; }}
  .cio {{ margin-top:14px; border-top:1px solid var(--border); padding-top:12px;
    border-left:3px solid var(--cyan); padding-left:12px; }}
  .cio-k {{ font-size:.68rem; color:var(--cyan); text-transform:uppercase;
    letter-spacing:.06em; font-weight:700; }}
  .cio p {{ margin:4px 0 0; color:var(--text); font-size:.9rem; }}
  .kick {{ color:var(--muted); font-size:.8125rem; margin:8px 0 16px; }}
  .grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:8px; }}
  .cell {{ display:flex; flex-direction:column; gap:2px; }}
  .k {{ font-size:.7rem; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }}
  .val {{ font-weight:600; }}
  .models {{ display:flex; flex-wrap:wrap; gap:6px; margin-top:14px;
    border-top:1px solid var(--border); padding-top:12px; }}
  .chip {{ font-size:.75rem; color:var(--muted); background:var(--surface-alt);
    border-radius:9999px; padding:3px 10px; }}
  .chip b {{ color:var(--text); }}
  footer {{ margin-top:40px; color:var(--muted); font-size:.8125rem;
    border-top:1px solid var(--border); padding-top:20px; }}
  @media (max-width:520px) {{ .grid {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
</head>
<body>
  <div class="wrap">
    <header class="top">
      <div class="eyebrow">Sports Quant Trading, {tournament}</div>
      <h1>Sugerencias del {date}</h1>
      <div class="meta">Estrategia <b>{strat}</b> ({crit}, Kelly x{kelly}), cuotas <b>{src}</b></div>
      <div class="summary">{summary}</div>
    </header>
    <section class="cards">{cards}</section>
    <footer>
      Generado por el agente el {html.escape(data.get('generated_at',''))}.
      Las probabilidades del modelo (Elo + Bayes + TrueSkill) se contrastan con el precio de Polymarket.
      No es consejo financiero, sólo señales cuantitativas para revisión.
    </footer>
  </div>
</body>
</html>"""
