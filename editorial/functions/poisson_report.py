"""Reporte HTML combinado: backtest del Poisson de goles + recomendaciones del día.

Tres secciones:
  1. Backtest Qatar 2022 (skill del modelo Poisson: BSS por mercado).
  2. Recomendaciones del día (match-winner, modelo vs Polymarket).
  3. Goles (Poisson): pronóstico de goles del día y mercados Over/Under, BTTS.

Design system pypro.mx ("Editor at Night"): dark, Operator Blue, cyan, Inter +
JetBrains Mono. Sin emojis-bullet ni em-dashes. Función pura.
"""
from __future__ import annotations

import html
from typing import Any

_VERDICT = {
    "AUTO": "#10B981", "REVIEW": "#F59E0B", "DISCARD": "#EF4444", "SKIP": "#94A3B8",
}
_VLABEL = {"AUTO": "Auto", "REVIEW": "Revisar", "DISCARD": "Descartar", "SKIP": "Saltar"}


def _pct(x: float | None) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/d"


# ── Sección 1: backtest ───────────────────────────────────────────────────────

def _backtest_rows(markets: dict[str, Any]) -> str:
    out = ""
    for name, m in markets.items():
        bss = m["bss"]
        color = "#22D3EE" if bss > 0 else "#94A3B8"
        flag = "skill" if bss > 0 else "sin skill"
        out += (
            f'<tr><td>{html.escape(name)}</td>'
            f'<td class="num">{m["n"]}</td>'
            f'<td class="num">{_pct(m["base_rate"])}</td>'
            f'<td class="num">{m["brier_model"]:.3f}</td>'
            f'<td class="num">{m["brier_base"]:.3f}</td>'
            f'<td class="num" style="color:{color};font-weight:700">{bss:+.3f}</td>'
            f'<td class="num">{_pct(m["acc_model"])}</td>'
            f'<td class="num muted">{_pct(m["acc_base"])}</td>'
            f'<td style="color:{color}">{flag}</td></tr>'
        )
    return out


# ── Sección 2: recomendaciones match-winner ──────────────────────────────────

def _suggestion_rows(rows: list[dict]) -> str:
    out = ""
    for r in rows:
        v = r.get("verdict", "SKIP")
        color = _VERDICT.get(v, "#94A3B8")
        edge = r.get("edge")
        edge_html = (f'<span class="num" style="color:{"#22D3EE" if (edge or 0) > 0 else "#94A3B8"}">'
                     f'{edge * 100:+.1f}%</span>' if edge is not None else '<span class="muted">n/d</span>')
        stake = r.get("stake") or 0.0
        stake_html = f'{stake:.2f}' if stake > 0 else '<span class="muted">0</span>'
        out += (
            f'<tr><td>{html.escape(r["home"])} <span class="muted">vs</span> {html.escape(r["away"])}</td>'
            f'<td><b>{html.escape(str(r.get("pick_team", "")))}</b></td>'
            f'<td class="num">{_pct(r.get("model_prob"))}</td>'
            f'<td class="num">{_pct(r.get("market_prob"))}</td>'
            f'<td class="num">{edge_html}</td>'
            f'<td><span class="badge" style="color:{color};border-color:{color}55">{_VLABEL.get(v, v)}</span></td>'
            f'<td class="num">{stake_html}</td></tr>'
        )
    return out


# ── Sección 3: goles (Poisson) ────────────────────────────────────────────────

def _goal_card(g: dict) -> str:
    res = g["result"]
    scores = ", ".join(f'{i}-{j} <span class="muted">({p*100:.0f}%)</span>'
                       for i, j, p in g["top_scores"])
    over = g["over25"]
    over_color = "#22D3EE" if over >= 0.5 else "#E2E8F0"
    return f"""
      <article class="gcard">
        <header class="gh">
          <div class="gmatch">{html.escape(g["home"])} <span class="muted">vs</span> {html.escape(g["away"])}</div>
          <span class="conf">conf {html.escape(g["confidence"])}</span>
        </header>
        <div class="lambdas">
          <span class="lam">{html.escape(g["home"])} <b class="num">{g["lambda_home"]:.2f}</b></span>
          <span class="muted">goles esperados</span>
          <span class="lam"><b class="num">{g["lambda_away"]:.2f}</b> {html.escape(g["away"])}</span>
          <span class="total num">total {g["total"]:.2f}</span>
        </div>
        <div class="gmarkets">
          <div class="gm"><span class="gk">Over 2.5</span><b class="num" style="color:{over_color}">{_pct(over)}</b></div>
          <div class="gm"><span class="gk">Under 2.5</span><b class="num">{_pct(1 - over)}</b></div>
          <div class="gm"><span class="gk">BTTS</span><b class="num">{_pct(g["btts"])}</b></div>
          <div class="gm"><span class="gk">1X2 goles</span><b class="num">{_pct(res["home"])}/{_pct(res["draw"])}/{_pct(res["away"])}</b></div>
        </div>
        <div class="scores"><span class="gk">Marcadores</span> {scores}</div>
      </article>"""


def build_poisson_report(*, backtest_res: dict, backtest_title: str,
                         suggestions: dict, goal_rows: list[dict],
                         date: str, generated_at: str) -> str:
    bt = _backtest_rows(backtest_res["markets"])
    sugg = _suggestion_rows(suggestions.get("rows", [])) or \
        '<tr><td colspan="7" class="muted">Sin partidos.</td></tr>'
    goals = "".join(_goal_card(g) for g in goal_rows) or \
        '<p class="muted">Sin partidos programados.</p>'
    d = html.escape(date)

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reporte Poisson de goles, WC {d}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
 :root{{--bg:#0F1117;--surface:#1A1D27;--surface-alt:#22262F;--border:#2D3340;
   --text:#E2E8F0;--muted:#94A3B8;--blue:#2563EB;--cyan:#22D3EE}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);
   font-family:Inter,system-ui,sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased}}
 .wrap{{max-width:1000px;margin:0 auto;padding:48px 24px 72px}}
 .num{{font-family:'JetBrains Mono',ui-monospace,monospace}} .muted{{color:var(--muted)}}
 header.top{{border-bottom:1px solid var(--border);padding-bottom:24px;margin-bottom:8px}}
 .eyebrow{{font-size:.75rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--cyan)}}
 h1{{font-size:2.2rem;font-weight:800;letter-spacing:-.02em;margin:.3rem 0 .4rem}}
 .meta{{color:var(--muted);font-size:.9rem}}
 section{{margin-top:44px}}
 h2{{font-size:1.4rem;font-weight:700;letter-spacing:-.01em;margin:0 0 4px;
   display:flex;align-items:baseline;gap:12px}}
 h2 .n{{font-size:.8rem;color:var(--cyan);font-family:'JetBrains Mono',monospace}}
 .sec-sub{{color:var(--muted);font-size:.9rem;margin:0 0 16px;max-width:720px}}
 table{{width:100%;border-collapse:collapse;font-size:.85rem}}
 th{{text-align:left;color:var(--muted);font-weight:600;font-size:.68rem;text-transform:uppercase;
   letter-spacing:.04em;padding:9px 8px;border-bottom:1px solid var(--border)}}
 td{{padding:9px 8px;border-bottom:1px solid var(--border)}}
 .num.td,td.num{{font-family:'JetBrains Mono',monospace}}
 .tbl{{border:1px solid var(--border);border-radius:12px;overflow:hidden}}
 .badge{{font-size:.68rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;
   border:1px solid;border-radius:9999px;padding:3px 10px;white-space:nowrap}}
 .note{{margin-top:14px;border-left:3px solid var(--cyan);padding:10px 14px;background:#22D3EE0c;
   border-radius:0 8px 8px 0;font-size:.88rem}}
 .note b{{color:var(--cyan)}}
 .gcards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:16px}}
 .gcard{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px 20px}}
 .gh{{display:flex;justify-content:space-between;align-items:baseline;gap:10px}}
 .gmatch{{font-size:1.05rem;font-weight:700}}
 .conf{{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}
 .lambdas{{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:10px 0;
   padding:10px 0;border-top:1px solid var(--border);border-bottom:1px solid var(--border)}}
 .lam b{{font-size:1.25rem;color:var(--cyan)}} .total{{margin-left:auto;color:var(--muted)}}
 .gmarkets{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:6px 0}}
 .gm{{display:flex;flex-direction:column;gap:2px}}
 .gk{{font-size:.65rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
 .scores{{margin-top:10px;font-size:.82rem}}
 footer{{margin-top:48px;color:var(--muted);font-size:.8rem;border-top:1px solid var(--border);padding-top:20px}}
 @media(max-width:520px){{.gcards{{grid-template-columns:1fr}}.gmarkets{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body><div class="wrap">

 <header class="top">
   <div class="eyebrow">Sports Quant Trading, FIFA World Cup 2026</div>
   <h1>Modelo Poisson de goles, reporte del {d}</h1>
   <div class="meta">Backtest de skill + recomendaciones del dia (match-winner) + pronostico de goles.</div>
 </header>

 <section>
   <h2>1. Backtest del modelo <span class="n">{html.escape(backtest_title)}</span></h2>
   <p class="sec-sub">Predict-then-update: el modelo se re-ajusta solo con partidos previos
   y se compara contra el promedio (base rate). BSS (Brier Skill Score) mayor a 0 = el
   modelo predice goles mejor que el promedio.</p>
   <div class="tbl"><table><thead><tr>
     <th>Mercado</th><th>n</th><th>Base</th><th>Brier modelo</th><th>Brier base</th>
     <th>BSS</th><th>Acc modelo</th><th>Acc base</th><th></th>
   </tr></thead><tbody>{bt}</tbody></table></div>
   <div class="note"><b>Lectura honesta:</b> el modelo muestra skill en Over/Under 2.5
   (la linea principal), pero la muestra es chica (n={backtest_res['markets'].get('Over 2.5', {}).get('n', 0)})
   y ganarle al promedio NO es ganarle a la linea de Polymarket. No apostar hasta
   validar con forward-test (registrar prediccion vs linea live y medir ROI/CLV).</div>
 </section>

 <section>
   <h2>2. Recomendaciones del dia <span class="n">match-winner</span></h2>
   <p class="sec-sub">Estrategia activa {html.escape(str(suggestions.get('strategy', '')))}
   (Elo+Bayes+TrueSkill vs Polymarket). Cuotas {html.escape(str(suggestions.get('source', '')))}.</p>
   <div class="tbl"><table><thead><tr>
     <th>Partido</th><th>Pick</th><th>Modelo</th><th>Mercado</th><th>Edge</th>
     <th>Veredicto</th><th>Stake</th>
   </tr></thead><tbody>{sugg}</tbody></table></div>
 </section>

 <section>
   <h2>3. Goles <span class="n">Poisson</span></h2>
   <p class="sec-sub">Modelo complementario: predice goles, no ganador. Goles esperados
   por lado y probabilidades de Over/Under 2.5, BTTS, 1X2-por-goles y marcadores.
   Sede neutral (sin ventaja local).</p>
   <div class="gcards">{goals}</div>
 </section>

 <footer>
   Generado por el agente el {html.escape(generated_at)}. Modelos: match-winner
   (Elo+Bayes+TrueSkill) y goles (Poisson con shrinkage). No es consejo financiero.
 </footer>
</div></body></html>"""
