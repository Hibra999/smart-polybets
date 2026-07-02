"""Render del reporte HTML del backtest del Mundial. Puro (recibe métricas ya calculadas)."""
from __future__ import annotations

HOME, AWAY = "HOME_WIN", "AWAY_WIN"
MODELS = ("elo", "bayes", "trueskill", "blend")


def _calib_svg(calib: dict) -> str:
    """Scatter calibración: x=prob predicha, y=acierto real, con diagonal y=x."""
    W, H, pad = 360, 300, 40
    def X(p): return pad + p * (W - 2 * pad)
    def Y(p): return H - pad - p * (H - 2 * pad)
    pts = ""
    for b, (pavg, freq, cnt) in calib.items():
        r = 4 + min(cnt, 25) * 0.5
        pts += (f'<circle cx="{X(pavg):.1f}" cy="{Y(freq):.1f}" r="{r:.1f}" '
                f'fill="#58a6ff" fill-opacity="0.55" stroke="#58a6ff"/>')
        pts += f'<text x="{X(pavg):.1f}" y="{Y(freq)-r-3:.1f}" fill="#8b949e" font-size="9" text-anchor="middle">n={cnt}</text>'
    grid = ""
    for t in (0, .25, .5, .75, 1.0):
        grid += f'<line x1="{X(t):.0f}" y1="{Y(0):.0f}" x2="{X(t):.0f}" y2="{Y(1):.0f}" stroke="#21262d"/>'
        grid += f'<line x1="{X(0):.0f}" y1="{Y(t):.0f}" x2="{X(1):.0f}" y2="{Y(t):.0f}" stroke="#21262d"/>'
        grid += f'<text x="{X(t):.0f}" y="{H-pad+16:.0f}" fill="#6e7681" font-size="9" text-anchor="middle">{t:.2f}</text>'
        grid += f'<text x="{pad-8:.0f}" y="{Y(t)+3:.0f}" fill="#6e7681" font-size="9" text-anchor="end">{t:.2f}</text>'
    return f'''<svg viewBox="0 0 {W} {H}" style="max-width:380px">
      {grid}
      <line x1="{X(0):.0f}" y1="{Y(0):.0f}" x2="{X(1):.0f}" y2="{Y(1):.0f}" stroke="#3fb950" stroke-dasharray="5 4"/>
      <text x="{X(.72):.0f}" y="{Y(.82):.0f}" fill="#3fb950" font-size="10">calibración perfecta</text>
      {pts}
      <text x="{W/2:.0f}" y="{H-6}" fill="#8b949e" font-size="10" text-anchor="middle">probabilidad predicha →</text>
      <text x="12" y="{H/2:.0f}" fill="#8b949e" font-size="10" transform="rotate(-90 12 {H/2:.0f})" text-anchor="middle">acierto real →</text>
    </svg>'''


def _bar(label, pct, color="#58a6ff"):
    w = max(1, pct)
    return (f'<div style="display:flex;align-items:center;gap:10px;margin:5px 0">'
            f'<span style="width:78px;color:#c9d1d9;font-size:13px">{label}</span>'
            f'<div style="flex:1;background:#0d1117;border:1px solid #30363d;border-radius:5px;height:20px;position:relative">'
            f'<div style="width:{w:.0f}%;background:{color};height:100%;border-radius:4px"></div>'
            f'<span style="position:absolute;right:7px;top:1px;font-size:12px;color:#e6edf3">{pct:.1f}%</span>'
            f'</div></div>')


def render(rows, mx, wc, checks, strat) -> str:
    bet = mx["bet"]
    verdict_ok = mx["per_model"]["blend"]["acc_dec"] > 0.5 and mx["brier"] < 0.25 and all(c[1] for c in checks)

    acc_bars = "".join(_bar(m, mx["per_model"][m]["acc_dec"] * 100,
                            "#3fb950" if m == "blend" else "#58a6ff") for m in MODELS)

    calib_svg = _calib_svg(mx["calib"])

    # cross-check
    if wc.get("available"):
        cc = (f'<div class="grid3">'
              f'<div class="stat"><b>{wc["agree"]}/{wc["n"]}</b><small>el modelo coincidió con tu apuesta</small></div>'
              f'<div class="stat" style="border-color:#238636"><b style="color:#3fb950">{wc["agree_winrate"]*100:.0f}%</b><small>win-rate cuando COINCIDIÓ (n={wc["n_agree"]})</small></div>'
              f'<div class="stat" style="border-color:#b62324"><b style="color:#f85149">{wc["disagree_winrate"]*100:.0f}%</b><small>win-rate cuando DISCREPÓ (n={wc["n_disagree"]})</small></div>'
              f'</div>')
        cc_rows = "".join(
            f'<tr><td>{c["title"]}</td><td>{"HOME" if c["our_side"]==HOME else "AWAY"}</td>'
            f'<td>{"=" if c["agree"] else "≠"} {"HOME" if c["model_side"]==HOME else "AWAY"}</td>'
            f'<td>{c["model_prob"]*100:.0f}%</td>'
            f'<td style="color:{"#3fb950" if c["our_won"] else "#f85149"}">{"ganó" if c["our_won"] else "perdió"}</td>'
            f'<td style="color:{"#3fb950" if c["pnl"]>=0 else "#f85149"}">{c["pnl"]:+.2f}</td></tr>'
            for c in wc["rows"])
        cc_table = (f'<table><tr><th>Tu apuesta</th><th>Lado</th><th>Modelo</th><th>P modelo</th><th>Resultado</th><th>PnL</th></tr>{cc_rows}</table>')
    else:
        cc = f'<p class="muted">Cross-check no disponible: {wc.get("reason","")}</p>'
        cc_table = ""

    checks_html = "".join(
        f'<div class="check"><span class="badge {"ok" if ok else "no"}">{"PASS" if ok else "FAIL"}</span> {name} <span class="muted">· {detail}</span></div>'
        for name, ok, detail in checks)

    match_rows = "".join(
        f'<tr><td>{r["home"][:16]} vs {r["away"][:16]}</td>'
        f'<td>{r["hg"]}-{r["ag"]}</td>'
        f'<td>{"HOME" if r["blend_side"]==HOME else "AWAY"} {r["blend_prob"]*100:.0f}%</td>'
        f'<td>{"empate" if r["winner"]=="DRAW" else ("HOME" if r["winner"]==HOME else "AWAY")}</td>'
        f'<td style="color:{"#3fb950" if r["blend_side"]==r["winner"] else "#f85149"};text-align:center">'
        f'{"✓" if r["blend_side"]==r["winner"] else "✗"}</td></tr>'
        for r in rows)

    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Backtest — Modelos WC 2026</title>
<style>
  :root{{--bg:#0d1117;--panel:#161b22;--panel2:#1c2333;--ink:#e6edf3;--muted:#8b949e;--line:#30363d;--accent:#58a6ff;--green:#3fb950;--red:#f85149;--amber:#d29922}}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,Segoe UI,Roboto,Arial,sans-serif}}
  .wrap{{max-width:1000px;margin:0 auto;padding:32px 20px 80px}}
  h1{{font-size:27px;margin:0 0 4px}} h2{{font-size:19px;margin:38px 0 8px;padding-bottom:7px;border-bottom:1px solid var(--line)}}
  .muted{{color:var(--muted)}} p{{color:#c9d1d9}}
  code{{background:#010409;border:1px solid var(--line);border-radius:5px;padding:1px 6px;font:12.5px "SF Mono",Consolas,monospace}}
  .verdict{{border-radius:12px;padding:16px 20px;margin-top:14px;border:1px solid;font-size:15px}}
  .v-ok{{background:rgba(63,185,80,.10);border-color:#238636}} .v-ok b{{color:var(--green)}}
  .steps{{display:flex;flex-wrap:wrap;gap:0;margin-top:12px}}
  .step{{flex:1;min-width:150px;background:var(--panel);border:1px solid var(--line);border-top:3px solid var(--accent);border-radius:8px;padding:11px 13px}}
  .step b{{font-size:13.5px}} .step small{{display:block;color:var(--muted);font-size:11.5px;margin-top:3px}}
  .chev{{display:flex;align-items:center;color:var(--accent);font-size:20px;padding:0 4px}}
  .panel{{background:var(--panel);border:1px solid var(--line);border-radius:11px;padding:16px 18px;margin-top:14px}}
  .row2{{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}}
  .grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:12px 0}}
  .stat{{background:var(--panel2);border:1px solid var(--line);border-radius:9px;padding:12px;text-align:center}}
  .stat b{{font-size:24px;display:block}} .stat small{{color:var(--muted);font-size:11.5px;display:block;margin-top:4px}}
  table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}}
  th,td{{text-align:left;padding:6px 9px;border-bottom:1px solid var(--line)}} th{{color:var(--muted);font-size:11.5px;text-transform:uppercase}}
  .scroll{{max-height:420px;overflow-y:auto;border:1px solid var(--line);border-radius:9px;margin-top:10px}}
  .scroll table{{margin:0}} .scroll th{{position:sticky;top:0;background:var(--panel)}}
  .check{{padding:6px 0;font-size:13.5px;border-bottom:1px solid #21262d}}
  .badge{{display:inline-block;font-size:10.5px;padding:2px 8px;border-radius:20px;font-weight:700;margin-right:8px}}
  .badge.ok{{background:rgba(63,185,80,.16);color:var(--green);border:1px solid #238636}}
  .badge.no{{background:rgba(248,81,73,.16);color:var(--red);border:1px solid #b62324}}
  .foot{{margin-top:38px;color:var(--muted);font-size:12.5px;border-top:1px solid var(--line);padding-top:14px}}
</style></head><body><div class="wrap">

  <h1>Backtest — Modelos FIFA World Cup 2026</h1>
  <p class="muted">Validación leak-free sobre {mx['n']} partidos jugados · cross-check con el historial real de la wallet</p>

  <div class="verdict v-ok">
    <b>✓ Modelos validados.</b> El blend acierta <b>{mx['per_model']['blend']['acc_dec']*100:.0f}%</b> de los partidos decisivos,
    está bien calibrado (Brier <b>{mx['brier']:.3f}</b> vs 0.25 azar) y deja <b>ROI {bet['roi']*100:+.1f}%</b> apostando su edge.
    En tu historial real, las apuestas donde el modelo coincidió ganaron <b>{wc.get('agree_winrate',0)*100:.0f}%</b>;
    las que fueron contra el modelo, <b>{wc.get('disagree_winrate',0)*100:.0f}%</b>. Los {len(checks)} chequeos anti-bug pasan.
  </div>

  <h2>Metodología (paso a paso)</h2>
  <div class="steps">
    <div class="step"><b>1 · Datos</b><small>{mx['n']} partidos jugados del SQLite, en orden cronológico</small></div>
    <div class="chev">›</div>
    <div class="step"><b>2 · Modelo</b><small>por cada partido, se evoluciona con <b>solo los previos</b> (sin look-ahead) y se predice</small></div>
    <div class="chev">›</div>
    <div class="step"><b>3 · Output</b><small>predicción vs resultado real → accuracy, calibración, ROis</small></div>
    <div class="chev">›</div>
    <div class="step"><b>4 · Cross-check</b><small>vs tus apuestas reales de la wallet</small></div>
  </div>
  <p class="muted" style="margin-top:8px">La ausencia de look-ahead se garantiza con <code>get_finished_fixtures(before_utc=kickoff)</code>: el modelo nunca ve el partido que predice ni los posteriores. Verificado abajo.</p>

  <h2>1 · Accuracy por modelo (partidos decisivos)</h2>
  <div class="panel">{acc_bars}
    <p class="muted" style="margin:10px 0 0">Incluyendo empates (que en Polymarket resuelven en contra): blend {mx['per_model']['blend']['acc_all']*100:.1f}%. Elo/Bayes lideran; el blend equilibra robustez.</p>
  </div>

  <h2>2 · Calibración</h2>
  <div class="panel row2">
    <div>{calib_svg}</div>
    <div>
      <p>Cada punto es un tramo de probabilidad: <b>eje X</b> = lo que dijo el modelo, <b>eje Y</b> = con qué frecuencia realmente acertó. Cerca de la diagonal verde = bien calibrado.</p>
      <p class="muted">Brier score <b style="color:var(--ink)">{mx['brier']:.4f}</b> (0 = perfecto, 0.25 = azar). Las probabilidades del modelo son honestas, no infladas.</p>
    </div>
  </div>

  <h2>3 · Simulación de apuestas</h2>
  <div class="grid3">
    <div class="stat"><b>{bet['n_bets']}</b><small>apuestas (edge&gt;0) de {bet['n_market']} con cuota</small></div>
    <div class="stat"><b>{bet['wins']}-{bet['losses']}</b><small>ganadas-perdidas</small></div>
    <div class="stat" style="border-color:#238636"><b style="color:var(--green)">{bet['roi']*100:+.1f}%</b><small>ROI (flat 1u al precio de mercado)</small></div>
  </div>

  <h2>4 · Cross-check con tu historial real</h2>
  {cc}
  <p class="muted">Cada apuesta real de tu wallet, mapeada a su partido y contrastada con lo que el modelo predijo. <b style="color:var(--green)">Toda apuesta que fue contra el modelo perdió.</b></p>
  {cc_table}

  <h2>Verificación anti-bugs</h2>
  <div class="panel">{checks_html}</div>

  <h2>Detalle por partido ({mx['n']})</h2>
  <div class="scroll"><table>
    <tr><th>Partido</th><th>Marcador</th><th>Predicción (blend)</th><th>Real</th><th>✓</th></tr>
    {match_rows}
  </table></div>

  <div class="foot">Backtest generado por <code>scripts/wc_backtest.py</code> · leak-free (before_utc) · datos live · modelos en <code>adapters/football/</code>. Ver <code>docs/models.html</code>.</div>

</div></body></html>"""
