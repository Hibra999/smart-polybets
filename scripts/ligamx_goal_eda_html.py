#!/usr/bin/env python
"""Reporte HTML del EDA de goles de Liga MX → editorial/reports/liga_mx_2026/ligamx-goles-eda.html.

Recomputa desde la DB (match_timeline_event + favoritos del cierre) y grafica
las curvas de DECAY que gobiernan el theta trade:
  1. Supervivencia: P(0-0 vivo) y P(favorito sin anotar) por minuto.
  2. Riesgo acumulado: P(favorito ya anotó ≤ m) y P(roja ya salió ≤ m).
  3. Distribución de goles por bin de 15'.

Paleta de series validada (dataviz) sobre #0d1117: azul #388bfd / ámbar #bb8009.

    python scripts/ligamx_goal_eda_html.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()

from scripts.ligamx_goal_eda import favorites_by_match, load_timeline

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "editorial" / "reports" / "liga_mx_2026" / "ligamx-goles-eda.html"

BLUE, AMBER, GREEN, RED = "#388bfd", "#bb8009", "#3fb950", "#f85149"
INK, MUT, GRID, BORDER = "#e6edf3", "#8b949e", "#21262d", "#30363d"


def build_matches():
    events = load_timeline()
    favs = favorites_by_match()
    matches: dict[str, dict] = {}
    from datetime import date
    for e in events:
        m = matches.setdefault(e["espn_event_id"], {
            "date": date.fromisoformat(e["match_date"]),
            "home": e["home_team_id"], "away": e["away_team_id"],
            "goals": [], "reds": []})
        (m["reds"] if e["event_type"] == "red_card" else m["goals"]).append(e)
    for m in matches.values():
        info = favs.get((m["date"], frozenset((m["home"], m["away"]))))
        m["fav"] = info[0] if info else None
    return matches


def curves(matches):
    """Series por minuto 0..90: supervivencias y riesgos acumulados."""
    n = len(matches)
    fav_ms = [m for m in matches.values() if m["fav"]]
    xs = list(range(0, 91))
    s00, sfav, cfav, cred = [], [], [], []
    for cp in xs:
        s00.append(sum(1 for m in matches.values()
                       if not any(g["minute"] <= cp for g in m["goals"])) / n)
        ok = scored = 0
        for m in fav_ms:
            side = "home" if m["fav"] == m["home"] else "away"
            hit = any(g["side"] == side and g["minute"] <= cp for g in m["goals"])
            ok += not hit
            scored += hit
        sfav.append(ok / len(fav_ms))
        cfav.append(scored / len(fav_ms))
        cred.append(sum(1 for m in matches.values()
                        if any(r["minute"] <= cp for r in m["reds"])) / n)
    return xs, s00, sfav, cfav, cred


def line_chart(xs, series, *, ylabel, w=880, h=340, pct=True) -> str:
    """series: [(nombre, color, ys)] — líneas con label directo al final."""
    pad_l, pad_r, pad_t, pad_b = 52, 150, 16, 36
    def X(v): return pad_l + v / xs[-1] * (w - pad_l - pad_r)
    def Y(v): return h - pad_b - v * (h - pad_t - pad_b)
    fmt = (lambda v: f"{v:.0%}") if pct else (lambda v: f"{v:.2f}")
    grid = ""
    for i in range(5):
        gy = i / 4
        grid += (f'<line x1="{pad_l}" y1="{Y(gy):.1f}" x2="{w-pad_r}" y2="{Y(gy):.1f}" stroke="{GRID}"/>'
                 f'<text x="{pad_l-6}" y="{Y(gy)+3:.1f}" fill="{MUT}" font-size="10" text-anchor="end">{fmt(gy)}</text>')
    for mx in range(0, 91, 15):
        grid += (f'<line x1="{X(mx):.1f}" y1="{Y(0):.1f}" x2="{X(mx):.1f}" y2="{Y(1):.1f}" stroke="{GRID}"/>'
                 f'<text x="{X(mx):.1f}" y="{h-pad_b+15}" fill="{MUT}" font-size="10" text-anchor="middle">{mx}\'</text>')
    body = ""
    for name, col, ys in series:
        path = " ".join(f"{'M' if i == 0 else 'L'}{X(x):.1f},{Y(y):.1f}" for i, (x, y) in enumerate(zip(xs, ys)))
        body += (f'<path d="{path}" fill="none" stroke="{col}" stroke-width="2.2">'
                 f'<title>{name}</title></path>'
                 f'<text x="{X(xs[-1])+7:.1f}" y="{Y(ys[-1])+4:.1f}" fill="{col}" '
                 f'font-size="11" font-weight="600">{name} {fmt(ys[-1])}</text>')
        for mx in (30, 45, 60, 75):
            body += (f'<circle cx="{X(mx):.1f}" cy="{Y(ys[mx]):.1f}" r="3.4" fill="{col}">'
                     f'<title>{name} al min {mx}: {fmt(ys[mx])}</title></circle>')
    return (f'<svg viewBox="0 0 {w} {h}" role="img" style="width:100%">{grid}{body}'
            f'<text x="{(pad_l+w-pad_r)/2:.0f}" y="{h-4}" fill="{MUT}" font-size="11" '
            f'text-anchor="middle">minuto de juego →</text>'
            f'<text x="13" y="{h/2:.0f}" fill="{MUT}" font-size="11" '
            f'transform="rotate(-90 13 {h/2:.0f})" text-anchor="middle">{ylabel} →</text></svg>')


def bins_chart(matches) -> str:
    all_goals = [g for m in matches.values() for g in m["goals"]]
    bins, labels = [], []
    for b in range(0, 90, 15):
        labels.append(f"{b+1}-{b+15}")
        bins.append(sum(1 for g in all_goals
                        if b < (min(g["minute_base"], 90) if g["minute_base"] <= 90 else 90) <= b + 15
                        or (b == 75 and g["minute_base"] > 90)))
    total = sum(bins)
    rows = ""
    peak = max(bins)
    for lab, v in zip(labels, bins):
        pct = v / total
        w = pct / (peak / total) * 100
        hot = v == peak
        rows += (f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0" '
                 f'title="{lab}\': {v} goles ({pct:.1%})">'
                 f'<span style="width:56px;color:{INK};font-size:12px">{lab}\'</span>'
                 f'<div style="flex:1;background:#0d1117;border:1px solid {BORDER};border-radius:4px;height:18px">'
                 f'<div style="width:{w:.1f}%;background:{RED if hot else BLUE};height:100%;border-radius:3px 0 0 3px"></div></div>'
                 f'<span style="width:96px;color:{MUT};font-size:12px;text-align:right">{v} ({pct:.1%})</span></div>')
    return rows


def main() -> None:
    matches = build_matches()
    xs, s00, sfav, cfav, cred = curves(matches)
    n = len(matches)
    goals = sum(len(m["goals"]) for m in matches.values())
    reds_m = sum(1 for m in matches.values() if m["reds"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Liga MX — Decay de goles (EDA)</title>
<style>
  body{{background:#0d1117;color:{INK};font-family:-apple-system,'Segoe UI',sans-serif;
       margin:0;padding:32px 16px;line-height:1.5}}
  .wrap{{max-width:960px;margin:0 auto}}
  h1{{font-size:25px;margin:0 0 4px}} h2{{font-size:18px;margin:30px 0 10px}}
  .muted{{color:{MUT}}} small{{font-size:12px}}
  .banner{{border:1px solid #9e6a03;background:#bb800914;border-radius:8px;padding:12px 16px;margin:16px 0}}
  .grid{{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(160px,1fr))}}
  .stat,.panel{{background:#161b22;border:1px solid {BORDER};border-radius:8px;padding:12px 14px}}
  .stat b{{font-size:22px;display:block}} .stat small{{color:{MUT}}}
  .legend{{display:flex;gap:16px;font-size:12px;color:{MUT};margin:6px 0}}
  .sw{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}}
</style></head><body><div class="wrap">

<h1>Liga MX — Decay de goles y riesgo del theta trade</h1>
<div class="muted">EDA 2025/26 (ESPN, {n} partidos, {goals} goles) · favoritos por cierre de football-data ·
generado {now} · <code>python scripts/ligamx_goal_eda_html.py</code></div>

<div class="banner"><b style="color:{AMBER}">Liga MX es hostil para aguantar tarde:</b>
<small class="muted">3.10 goles/partido; el favorito ya anotó antes del min 30 en el
{cfav[30]:.0%} de los partidos, y el bin 76-90 es el más denso. El decaimiento útil vive temprano.
Detalle: docs/findings/2026-07-14-ligamx-goles-eda.md</small></div>

<div class="grid">
  <div class="stat"><b>{goals/n:.2f}</b><small>goles/partido</small></div>
  <div class="stat"><b>{s00[30]:.0%}</b><small>P(0-0 vivo) al min 30</small></div>
  <div class="stat"><b>{sfav[30]:.0%}</b><small>P(favorito sin anotar) al min 30</small></div>
  <div class="stat"><b>{sfav[90]:.0%}</b><small>P(favorito sin anotar) al 90'</small></div>
  <div class="stat"><b>{reds_m/n:.0%}</b><small>partidos con roja</small></div>
</div>

<h2>1. Supervivencia — las curvas de decay del theta</h2>
<div class="legend"><span><i class="sw" style="background:{BLUE}"></i>P(0-0 vivo)</span>
<span><i class="sw" style="background:{AMBER}"></i>P(favorito sin anotar) — la vida del trade</span></div>
<div class="panel">{line_chart(xs, [("0-0 vivo", BLUE, s00), ("fav sin anotar", AMBER, sfav)],
                               ylabel="probabilidad de seguir vivo")}
<small class="muted">La curva ámbar ES el trade: mientras el favorito no anota, el NO gana valor.
Cae rápido: 63% al min 30 → 47% al 45 → 32% al 60 → 18% al 90. Puntos marcados en 30/45/60/75.</small></div>

<h2>2. Riesgo acumulado — cuándo llega el gap</h2>
<div class="legend"><span><i class="sw" style="background:{RED}"></i>P(favorito YA anotó ≤ m) — el gap en contra</span>
<span><i class="sw" style="background:{GREEN}"></i>P(roja ya salió ≤ m) — volatilidad extra</span></div>
<div class="panel">{line_chart(xs, [("fav ya anotó", RED, cfav), ("roja salió", GREEN, cred)],
                               ylabel="probabilidad acumulada")}
<small class="muted">Verde/rojo aquí son STATUS (riesgo), no series categóricas — valores impresos en labels
y hover. Las rojas se concentran tarde (mediana min 74): tercer factor de volatilidad al final.</small></div>

<h2>3. Distribución de goles por bin de 15'</h2>
<div class="panel">{bins_chart(matches)}
<small class="muted">En rojo el bin más denso (76-90 + descuentos): exactamente donde el default
actual hard_exit 105 nos tendría adentro. Hipótesis a testear: salir en 60-75.</small></div>

<h2>Hipótesis de reglas para J1-J3 (no aplicadas — necesitan price paths)</h2>
<ol style="font-size:14px">
  <li><code>hard_exit_min</code> 60-75 en vez de 105 (evitar el bin 76-90).</li>
  <li><code>from_min</code> 20-25 con TP más agresivo (el theta útil vive temprano).</li>
  <li>Regla de rojas: salir si es al dog; aguantar (o ampliar TP) si es al favorito.</li>
</ol>
<div class="muted"><small>La decisión final cruza estas curvas con los ticks reales
(data/&lt;torneo&gt;/events/) — cuánto theta paga el mercado por minuto vs este hazard.</small></div>

</div></body></html>"""
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] {OUT}")


if __name__ == "__main__":
    main()
