#!/usr/bin/env python
"""Reporte HTML del backtest de Liga MX → docs/ligamx-backtest.html.

Recomputa el backtest (scripts/ligamx_backtest.py, sin red — lee MEX.csv) y los
seeds actuales de la DB, y renderiza el reporte con el estilo de la casa
(tema oscuro, SVG inline, mismo look que docs/wc-backtest.html).

Paleta de series validada (dataviz six-checks, superficie #0d1117):
  modelo = #388bfd (azul) · mercado = #bb8009 (ámbar); verde/rojo SOLO como
  status de PnL con el número impreso al lado (nunca color solo).

    python scripts/ligamx_backtest_html.py
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()

from scripts.ligamx_backtest import (
    bet_sim,
    calibrate_boundary_regression,
    calibrate_home_adv,
    eval_models,
    load_matches,
    market_implied_trajectory,
    trueskill_trajectory,
)

RHO, WARMUP = 0.80, 3  # mismos parámetros de producción que scripts/ligamx_backtest.py

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "ligamx-backtest.html"
DB = REPO / "data" / "liga_mx_2026" / "liga_mx_2026.sqlite"

BLUE, AMBER, GREEN, RED = "#388bfd", "#bb8009", "#3fb950", "#f85149"
INK, MUT, GRID, BORDER = "#e6edf3", "#8b949e", "#21262d", "#30363d"


def line_chart(points, *, best_x, xlabel, w=430, h=250, fmt_x=lambda v: f"{v:g}") -> str:
    """Línea Brier vs parámetro con el óptimo resaltado. Un eje, labels directos."""
    pad_l, pad_r, pad_t, pad_b = 56, 16, 14, 40
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    yr = (y1 - y0) or 1e-9
    y0, y1 = y0 - yr * 0.15, y1 + yr * 0.15

    def X(v): return pad_l + (v - x0) / (x1 - x0) * (w - pad_l - pad_r)
    def Y(v): return h - pad_b - (v - y0) / (y1 - y0) * (h - pad_t - pad_b)

    grid = ""
    for i in range(4):
        gy = y0 + (y1 - y0) * i / 3
        grid += (f'<line x1="{pad_l}" y1="{Y(gy):.1f}" x2="{w-pad_r}" y2="{Y(gy):.1f}" stroke="{GRID}"/>'
                 f'<text x="{pad_l-6}" y="{Y(gy)+3:.1f}" fill="{MUT}" font-size="10" text-anchor="end">{gy:.4f}</text>')
    path = " ".join(f"{'M' if i == 0 else 'L'}{X(px):.1f},{Y(py):.1f}" for i, (px, py) in enumerate(points))
    dots = ""
    for px, py in points:
        is_best = (px == best_x)
        r = 6 if is_best else 3.5
        col = GREEN if is_best else BLUE
        dots += (f'<circle cx="{X(px):.1f}" cy="{Y(py):.1f}" r="{r}" fill="{col}">'
                 f'<title>{xlabel}={fmt_x(px)} · Brier {py:.5f}</title></circle>')
        if is_best:
            dots += (f'<text x="{X(px):.1f}" y="{Y(py)-11:.1f}" fill="{GREEN}" font-size="11" '
                     f'text-anchor="middle" font-weight="600">óptimo {fmt_x(px)}</text>')
    ticks = "".join(
        f'<text x="{X(px):.1f}" y="{h-pad_b+16}" fill="{MUT}" font-size="10" text-anchor="middle">{fmt_x(px)}</text>'
        for px in xs[:: max(1, len(xs)//7)])
    return (f'<svg viewBox="0 0 {w} {h}" role="img" style="max-width:{w}px;width:100%">{grid}'
            f'<path d="{path}" fill="none" stroke="{BLUE}" stroke-width="2"/>{dots}{ticks}'
            f'<text x="{(pad_l+w-pad_r)/2:.0f}" y="{h-6}" fill="{MUT}" font-size="11" text-anchor="middle">{xlabel} →</text>'
            f'<text x="14" y="{h/2:.0f}" fill="{MUT}" font-size="11" transform="rotate(-90 14 {h/2:.0f})" text-anchor="middle">Brier (menor = mejor) →</text></svg>')


def pair_bars(title, model_v, market_v, *, fmt=lambda v: f"{v:.5f}") -> str:
    """Dos barras horizontales (modelo vs mercado), escala propia, labels directos."""
    lo = min(model_v, market_v) * 0.985
    hi = max(model_v, market_v) * 1.005
    def W(v): return max(4, (v - lo) / (hi - lo) * 100)
    def row(name, v, col):
        return (f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0">'
                f'<span style="width:64px;color:{MUT};font-size:12px">{name}</span>'
                f'<div style="flex:1;background:#0d1117;border:1px solid {BORDER};border-radius:4px;height:18px">'
                f'<div style="width:{W(v):.1f}%;background:{col};height:100%;border-radius:3px 0 0 3px"></div></div>'
                f'<span style="width:64px;color:{INK};font-size:12px;text-align:right">{fmt(v)}</span></div>')
    winner = "mercado" if market_v < model_v else "modelo"
    return (f'<div class="panel"><h4>{title}</h4>{row("modelo", model_v, BLUE)}'
            f'{row("mercado", market_v, AMBER)}'
            f'<small style="color:{MUT}">gana <b style="color:{AMBER if winner=="mercado" else BLUE}">{winner}</b> (menor = mejor)</small></div>')


def roi_bar(roi: float) -> str:
    pct = roi * 100
    w = min(48, abs(pct) * 9)
    col = GREEN if pct >= 0 else RED
    side = ("margin-left:50%" if pct >= 0 else f"margin-left:{50-w:.1f}%")
    return (f'<div style="position:relative;background:#0d1117;border:1px solid {BORDER};'
            f'border-radius:4px;height:16px;min-width:130px">'
            f'<div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:{BORDER}"></div>'
            f'<div style="{side};width:{w:.1f}%;background:{col};height:100%;border-radius:3px"></div></div>')


def seeds_chart(seeds: list[tuple[str, float]]) -> str:
    """Divergente alrededor de 1500 (la media de la liga): azul arriba, ámbar abajo."""
    rows = ""
    for team, elo in seeds:
        d = elo - 1500.0
        w = min(46, abs(d) / 3.2)
        col = BLUE if d >= 0 else AMBER
        side = "margin-left:50%" if d >= 0 else f"margin-left:{50-w:.1f}%"
        extra = " · sin historia (reemplaza a Mazatlán)" if team == "atlante" else ""
        rows += (f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0" title="{team}: {elo:.1f}{extra}">'
                 f'<span style="width:130px;color:{INK};font-size:12px">{team}{"*" if team == "atlante" else ""}</span>'
                 f'<div style="position:relative;flex:1;background:#0d1117;border:1px solid {BORDER};border-radius:4px;height:15px">'
                 f'<div style="position:absolute;left:50%;top:0;bottom:0;width:1px;background:{BORDER}"></div>'
                 f'<div style="{side};width:{w:.1f}%;background:{col};height:100%;border-radius:3px"></div></div>'
                 f'<span style="width:52px;color:{MUT};font-size:12px;text-align:right">{elo:.0f}</span></div>')
    return rows


HILITE = ["#388bfd", "#bb8009", "#2ea043", "#a371f7"]  # validada (dataviz) sobre #0d1117


def rolling(vals: list[float], win: int = 3) -> list[float]:
    return [sum(vals[max(0, i - win + 1):i + 1]) / len(vals[max(0, i - win + 1):i + 1])
            for i in range(len(vals))]


def team_lines_chart(traj: dict[str, list[float]], *, ylabel: str,
                     fmt=lambda v: f"{v:.1f}", w=920, h=380) -> str:
    """Multilínea por equipo/fecha: líneas de contexto en gris, top-4 por valor
    final destacados con label directo (identidad nunca sólo por color: hover
    <title> en todas + labels)."""
    pad_l, pad_r, pad_t, pad_b = 52, 130, 14, 34
    n_max = max(len(v) for v in traj.values())
    ys = [v for vals in traj.values() for v in vals]
    y0, y1 = min(ys), max(ys)
    yr = (y1 - y0) or 1e-9
    y0, y1 = y0 - yr * 0.06, y1 + yr * 0.10

    def X(i): return pad_l + i / (n_max - 1) * (w - pad_l - pad_r)
    def Y(v): return h - pad_b - (v - y0) / (y1 - y0) * (h - pad_t - pad_b)

    top4 = [t for t, _ in sorted(traj.items(), key=lambda kv: -kv[1][-1])[:4]]
    grid = ""
    for i in range(5):
        gy = y0 + (y1 - y0) * i / 4
        grid += (f'<line x1="{pad_l}" y1="{Y(gy):.1f}" x2="{w-pad_r}" y2="{Y(gy):.1f}" stroke="{GRID}"/>'
                 f'<text x="{pad_l-6}" y="{Y(gy)+3:.1f}" fill="{MUT}" font-size="10" text-anchor="end">{fmt(gy)}</text>')
    for j in range(0, n_max, 4):
        grid += f'<text x="{X(j):.1f}" y="{h-pad_b+15}" fill="{MUT}" font-size="10" text-anchor="middle">{j}</text>'

    lines = labels = ""
    for team, vals in sorted(traj.items(), key=lambda kv: kv[1][-1]):
        path = " ".join(f"{'M' if i == 0 else 'L'}{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
        tip = f"<title>{team}: {fmt(vals[0])} → {fmt(vals[-1])}</title>"
        if team in top4:
            col = HILITE[top4.index(team)]
            lines += f'<path d="{path}" fill="none" stroke="{col}" stroke-width="2.2">{tip}</path>'
            labels += (f'<text x="{X(len(vals)-1)+6:.1f}" y="{Y(vals[-1])+4:.1f}" fill="{col}" '
                       f'font-size="11" font-weight="600">{team} {fmt(vals[-1])}</text>')
        else:
            lines += f'<path d="{path}" fill="none" stroke="#30363d" stroke-width="1.1">{tip}</path>'
    return (f'<svg viewBox="0 0 {w} {h}" role="img" style="width:100%">{grid}{lines}{labels}'
            f'<text x="{(pad_l+w-pad_r)/2:.0f}" y="{h-4}" fill="{MUT}" font-size="11" '
            f'text-anchor="middle">fecha jugada por el equipo (temporada 2025/26) →</text>'
            f'<text x="12" y="{h/2:.0f}" fill="{MUT}" font-size="11" '
            f'transform="rotate(-90 12 {h/2:.0f})" text-anchor="middle">{ylabel} →</text></svg>')


def main() -> None:
    print("Recomputando backtest (sin red, lee MEX.csv)…")
    cal = load_matches({"2022/2023", "2023/2024", "2024/2025", "2025/2026"})
    burn = sum(1 for m in cal if m["season"] == "2022/2023")
    grid_adv = calibrate_home_adv(cal, burn)
    best_adv = min(grid_adv, key=lambda t: t[1])[0]
    grid_rho = calibrate_boundary_regression(cal, burn, best_adv)

    history = load_matches({"2023/2024", "2024/2025"})
    target = load_matches({"2025/2026"})
    q = eval_models(history, target, best_adv, rho=RHO, warmup=WARMUP)
    sims = [bet_sim(history, target, ev_min=e, rho=RHO, warmup=WARMUP)
            for e in (0.02, 0.05, 0.10, 0.15)]
    traj = trueskill_trajectory(history, target, best_adv, rho=RHO)
    odds_traj = {t: rolling(v) for t, v in market_implied_trajectory(target).items()}

    con = sqlite3.connect(DB)
    seeds = sorted(con.execute(
        "SELECT id, elo_rating FROM team WHERE tournament_id='liga_mx_2026'"),
        key=lambda r: -r[1])
    con.close()

    sim_rows = "".join(
        f'<tr><td>EV ≥ {s["ev_min"]:.2f}</td><td>{s["n_bets"]}</td><td>{s["wins"]}</td>'
        f'<td>${s["staked"]:,.0f}</td>'
        f'<td style="color:{GREEN if s["pnl"] >= 0 else RED}">{s["pnl"]:+,.2f}</td>'
        f'<td><div style="display:flex;align-items:center;gap:8px">{roi_bar(s["roi_staked"])}'
        f'<span style="color:{GREEN if s["roi_staked"] >= 0 else RED}">{s["roi_staked"]:+.1%}</span></div></td>'
        f'<td>{s["max_dd"]:.0%}</td></tr>'
        for s in sims)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Backtest Liga MX Apertura 2026</title>
<style>
  body{{background:#0d1117;color:{INK};font-family:-apple-system,'Segoe UI',sans-serif;
       margin:0;padding:32px 16px;line-height:1.5}}
  .wrap{{max-width:960px;margin:0 auto}}
  h1{{font-size:26px;margin:0 0 4px}} h2{{font-size:19px;margin:34px 0 10px;color:{INK}}}
  h4{{margin:0 0 8px;font-size:13px;color:{MUT};font-weight:600}}
  .muted{{color:{MUT}}} small{{font-size:12px}}
  .banner{{border:1px solid #b62324;background:#f851491a;border-radius:8px;padding:12px 16px;margin:18px 0}}
  .grid{{display:grid;gap:12px}} .g3{{grid-template-columns:repeat(auto-fit,minmax(170px,1fr))}}
  .g2{{grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}}
  .stat,.panel{{background:#161b22;border:1px solid {BORDER};border-radius:8px;padding:12px 14px}}
  .stat b{{font-size:22px;display:block}} .stat small{{color:{MUT}}}
  table{{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0}}
  th,td{{border:1px solid {BORDER};padding:6px 9px;text-align:left}}
  th{{background:#161b22;color:{MUT};font-weight:600}}
  .legend{{display:flex;gap:16px;font-size:12px;color:{MUT};margin:6px 0}}
  .sw{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}}
</style></head><body><div class="wrap">

<h1>Backtest — Liga MX Apertura 2026</h1>
<div class="muted">Datos: football-data.co.uk (MEX.csv, cuotas de cierre) · walk-forward sin lookahead ·
generado {now} · <code>python scripts/ligamx_backtest_html.py</code></div>

<div class="banner"><b style="color:{RED}">Veredicto: SIN edge contra las cuotas de cierre → estrategia en DRAFT.</b><br>
<small class="muted">El mercado le gana a Elo y Poisson en todas las métricas. Si hay edge en Polymarket será por
precios blandos del venue (mercado abierto el 2026-07-13), no por el modelo — a validar en J1–J3.</small></div>

<div class="grid g3">
  <div class="stat"><b>{len(target)}</b><small>partidos 2025/26 (objetivo)</small></div>
  <div class="stat"><b>{len(cal)}</b><small>partidos en calibración (4 temporadas)</small></div>
  <div class="stat"><b>+{best_adv:.0f} Elo</b><small>localía calibrada</small></div>
  <div class="stat"><b>ρ = 0.80</b><small>regresión entre torneos cortos</small></div>
  <div class="stat"><b>1.40</b><small>home_factor Poisson (2025/26)</small></div>
</div>

<h2>A. Calibración de la localía</h2>
<div class="grid g2">
  <div class="panel"><h4>Brier vs ventaja de localía (puntos Elo)</h4>
    {line_chart(grid_adv, best_x=best_adv, xlabel="home_adv (pts Elo)", fmt_x=lambda v: f"{v:.0f}")}
  </div>
  <div class="panel"><h4>Brier vs regresión ρ en fronteras Apertura/Clausura</h4>
    {line_chart(sorted(grid_rho), best_x=0.80, xlabel="ρ (fuerza conservada)", fmt_x=lambda v: f"{v:.2f}")}
    <small class="muted">Los torneos cortos reinician la <b>tabla</b>, no la fuerza: el reset total (ρ→0.5)
    empeora, el continuo puro (ρ=1) también. Óptimo: conservar ~80%.</small>
  </div>
</div>

<h2>B. Modelos vs mercado de cierre — 2025/26 ({q['n_odds']} partidos evaluados)</h2>
<p class="muted"><small>Condiciones de producción: <b>warmup de {WARMUP} fechas</b> por equipo y por torneo corto
({q['skipped_warmup']} partidos excluidos) + <b>regresión del 20%</b> a la media (ρ={RHO}) en cada frontera
Apertura/Clausura.</small></p>
<div class="legend"><span><i class="sw" style="background:{BLUE}"></i>modelo</span>
<span><i class="sw" style="background:{AMBER}"></i>mercado (cierre promedio)</span></div>
<div class="grid g3">
  {pair_bars("Elo — Brier binario (1/0.5/0)", q['elo_brier'], q['market_brier_bin'])}
  {pair_bars("Poisson 1X2 — Brier 3-clases", q['poisson_brier3'], q['market_brier3'])}
  {pair_bars("Poisson 1X2 — log-loss", q['poisson_logloss'], q['market_logloss'], fmt=lambda v: f"{v:.4f}")}
</div>
<p class="muted"><small>El mercado gana en las tres métricas: las cuotas de cierre son más afiladas que
nuestros modelos. Cualquier "edge" del modelo contra el cierre es mayormente ilusorio.</small></p>

<h2>C. Simulación de apuestas — Poisson 1X2 vs cierre (¼ Kelly, max $25, bankroll $1,000; warmup {WARMUP} fechas + ρ={RHO})</h2>
<table>
<tr><th>Umbral</th><th>Apuestas</th><th>Ganadas</th><th>Apostado</th><th>PnL</th><th>ROI / apostado</th><th>Max DD</th></tr>
{sim_rows}
</table>
<p class="muted"><small>Umbral bajo = pérdida clara; el +0.6% de EV≥0.15 con 122 apuestas es ruido estadístico,
no evidencia de edge.</small></p>

<h2>Evolución TrueSkill por equipo — temporada 2025/26</h2>
<div class="panel">{team_lines_chart(traj, ylabel="μ TrueSkill")}
<small class="muted">18 equipos (gris = contexto; hover para identificar). Destacados los 4 con mayor μ final.
TrueSkill sembrado del Elo al inicio de la temporada (con ρ={RHO}) y actualizado partido a partido.
Es la vista "qué piensa el <b>modelo</b> de cada equipo".</small></div>

<h2>Cuotas del mercado por equipo — temporada 2025/26</h2>
<div class="panel">{team_lines_chart(odds_traj, ylabel="P(victoria) implícita del cierre", fmt=lambda v: f"{v:.0%}")}
<small class="muted">Probabilidad de victoria implícita en las cuotas de cierre (promedio, sin vig) en cada
fecha del equipo, suavizada con media móvil de 3 partidos (el valor crudo depende del rival de turno).
Destacados los 4 con mayor valor final. Es la vista "qué piensa el <b>mercado</b> de cada equipo" —
el espejo del gráfico TrueSkill de arriba: donde ambas curvas divergen es donde habría (o habríamos
creído tener) señal.</small></div>

<h2>Seeds de Elo para el Apertura 2026 (tras regresión ρ=0.80)</h2>
<div class="legend"><span><i class="sw" style="background:{BLUE}"></i>arriba de la media (1500)</span>
<span><i class="sw" style="background:{AMBER}"></i>debajo de la media</span></div>
<div class="panel">{seeds_chart([(t, e) for t, e in seeds])}
<small class="muted">* Atlante entra por Mazatlán y no hereda su historia → arranca en la media.</small></div>

<h2>Plan (decisión del CIO pendiente)</h2>
<ol style="font-size:14px">
  <li><b>J1–J3 en modo observación</b>: registrar precio Polymarket vs Poisson vs cierre (MEX.csv se actualiza semanal).</li>
  <li>Aprobar <code>match_winner_ligamx_v1</code> <b>solo</b> con evidencia de que Polymarket precia peor que el cierre;
      umbral de edge ≥ 0.10 y sizing chico.</li>
  <li>Rutina diaria: <code>fetch_fixtures_pm.py --apply</code> + <code>update_results.py --tournament liga_mx_2026 --apply</code>.</li>
</ol>
<div class="muted"><small>Detalle y decisiones: docs/findings/2026-07-14-ligamx-backtest.md ·
tournaments/liga_mx_2026/TOURNAMENT.md</small></div>

</div></body></html>"""
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] {OUT}")


if __name__ == "__main__":
    main()
