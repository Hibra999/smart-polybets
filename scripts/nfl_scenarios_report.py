#!/usr/bin/env python
"""Corre la matriz completa de escenarios de backtest NFL y genera un HTML.

Grid: modelo (elo/bayes/trueskill/blend) x lado (favorito/underdog) x línea
(real/sin-vig) x reset (carryover/per-season), Kelly 0.4, en 4 temporadas + avg.
Guarda un reporte con la matriz coloreada por yield.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()  # consola Windows: stdout/stderr en UTF-8

from agent.workflows import nfl_ensemble_backtest as eb
from editorial.functions.report_builder import save_report

SEASONS = [2022, 2023, 2024, 2025]
MODELS = {"elo": {"elo": 1}, "bayes": {"bayes": 1}, "trueskill": {"trueskill": 1},
          "blend": {"elo": 1, "trueskill": 1, "bayes": 1}}


def _color(y: float | None) -> str:
    if y is None:
        return "background:transparent;color:#94A3B8"
    cap = max(-0.20, min(0.20, y)) / 0.20         # -1..1
    if y >= 0:
        a = 0.10 + 0.35 * cap
        return f"background:rgba(16,185,129,{a:.2f});color:#E2E8F0"
    a = 0.10 + 0.35 * (-cap)
    return f"background:rgba(239,68,68,{a:.2f});color:#E2E8F0"


def run() -> None:
    games = eb.load_games()
    rows = []
    for reset in (True, False):
        for dogs in (True, False):
            for dv in (False, True):
                for name, w in MODELS.items():
                    ys, tb = [], 0
                    for s in SEASONS:
                        m = eb.simulate_combo(games, w, season=s, devig=dv, edge_threshold=0.0,
                                              kelly_fraction=0.4, underdogs_only=dogs,
                                              per_season_reset=reset)
                        ys.append(m["yield"]); tb += m["n_bets"]
                    avg = sum(ys) / len(ys)
                    rows.append({
                        "model": name, "side": "Underdog" if dogs else "Favorito",
                        "line": "Sin vig" if dv else "Real", "reset": "Reset/año" if reset else "Carryover",
                        "ys": ys, "avg": avg, "bets": tb,
                    })
    rows.sort(key=lambda r: r["avg"], reverse=True)

    body = ""
    for r in rows:
        cells = "".join(f'<td class="num" style="{_color(y)}">{y * 100:+.1f}%</td>' for y in r["ys"])
        body += (f'<tr><td>{r["model"]}</td><td>{r["side"]}</td><td>{r["line"]}</td>'
                 f'<td class="muted">{r["reset"]}</td>{cells}'
                 f'<td class="num" style="{_color(r["avg"])};font-weight:700">{r["avg"] * 100:+.1f}%</td>'
                 f'<td class="num muted">{r["bets"]}</td></tr>')

    pos = sum(1 for r in rows if r["avg"] > 0)
    html = f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Escenarios NFL backtest</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
 :root{{--bg:#0F1117;--surface:#1A1D27;--border:#2D3340;--text:#E2E8F0;--muted:#94A3B8;--cyan:#22D3EE}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,sans-serif}}
 .wrap{{max-width:1000px;margin:0 auto;padding:48px 24px}}
 .num{{font-family:'JetBrains Mono',monospace}} .muted{{color:var(--muted)}}
 .eyebrow{{font-size:.75rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--cyan)}}
 h1{{font-size:2rem;font-weight:700;letter-spacing:-.015em;margin:.25rem 0}}
 .sub{{color:var(--muted);font-size:.9rem;margin-bottom:20px}}
 table{{width:100%;border-collapse:collapse;font-size:.82rem}}
 th{{text-align:left;color:var(--muted);font-weight:600;font-size:.68rem;text-transform:uppercase;letter-spacing:.04em;padding:8px;border-bottom:1px solid var(--border)}}
 td{{padding:6px 8px;border-bottom:1px solid var(--border)}}
 .scroll{{border:1px solid var(--border);border-radius:12px;overflow:hidden}}
 footer{{margin-top:24px;color:var(--muted);font-size:.8rem;border-top:1px solid var(--border);padding-top:16px}}
</style></head><body><div class="wrap">
 <div class="eyebrow">Sports Quant Trading, NFL</div>
 <h1>Matriz de escenarios, backtest NFL</h1>
 <div class="sub">{len(rows)} escenarios (modelo x lado x linea x reset), Kelly 0.4, edge_thr 0, ordenado por yield promedio. {pos}/{len(rows)} con promedio positivo.</div>
 <div class="scroll"><table><thead><tr>
   <th>Modelo</th><th>Lado</th><th>Linea</th><th>Reset</th>
   <th>2022</th><th>2023</th><th>2024</th><th>2025</th><th>AVG</th><th>Bets</th>
 </tr></thead><tbody>{body}</tbody></table></div>
 <footer>Yield (profit/total apostado) por temporada. Verde=positivo, rojo=negativo. Validacion out-of-sample: ningun escenario es positivo en las 4 temporadas. No es consejo financiero.</footer>
</div></body></html>"""
    path = save_report("nfl_2026", html, suffix="scenarios", ext="html")
    print(f"Escenarios: {len(rows)} | con AVG positivo: {pos} | HTML: {path}")


if __name__ == "__main__":
    run()
