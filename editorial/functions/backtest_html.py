"""Reporte HTML de un backtest NFL (TrueSkill + Kelly) con logos.

Design system pypro.mx (dark). Recibe el dict de nfl_backtest.simulate() y un mapa
{team_code: data_uri_del_logo}. Función pura: devuelve HTML.
"""
from __future__ import annotations

import html
from typing import Any


def _curve_svg(curve: list[float], bankroll0: float, w: int = 900, h: int = 220) -> str:
    if len(curve) < 2:
        return ""
    lo, hi = min(curve + [bankroll0]), max(curve + [bankroll0])
    span = (hi - lo) or 1.0
    n = len(curve)

    def x(i: int) -> float:
        return i / (n - 1) * w

    def y(v: float) -> float:
        return h - (v - lo) / span * h

    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(curve))
    base_y = y(bankroll0)
    final = curve[-1]
    color = "#10B981" if final >= bankroll0 else "#EF4444"
    return f"""<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none" style="display:block">
      <line x1="0" y1="{base_y:.1f}" x2="{w}" y2="{base_y:.1f}" stroke="#3D4452" stroke-width="1" stroke-dasharray="4 4"/>
      <polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>
    </svg>"""


def _logo(code: str, logos: dict[str, str], size: int = 22) -> str:
    uri = logos.get(code)
    if uri:
        return f'<img src="{uri}" width="{size}" height="{size}" alt="{html.escape(code)}" style="vertical-align:middle;border-radius:4px">'
    return f'<span class="num">{html.escape(code)}</span>'


def _metric(label: str, value: str, color: str = "#E2E8F0") -> str:
    return (f'<div class="metric"><span class="m-label">{label}</span>'
            f'<span class="m-val num" style="color:{color}">{value}</span></div>')


def build_backtest_html(res: dict[str, Any], logos: dict[str, str]) -> str:
    pos = res["profit"] >= 0
    pcol = "#10B981" if pos else "#EF4444"
    metrics = "".join([
        _metric("Bankroll final", f"${res['bankroll_final']:.2f}", pcol),
        _metric("Profit", f"${res['profit']:+.2f}", pcol),
        _metric("ROI", f"{res['roi'] * 100:+.1f}%", pcol),
        _metric("Yield", f"{res['yield'] * 100:+.1f}%", pcol),
        _metric("Apuestas", str(res["n_bets"])),
        _metric("Aciertos", f"{res['wins']} ({res['win_rate'] * 100:.0f}%)"),
        _metric("Max drawdown", f"${res['max_drawdown']:.2f}", "#F59E0B"),
    ])

    rows = []
    for b in res["bets"]:
        won = b["won"]
        rc = "#10B981" if won else "#EF4444"
        wk = html.escape(str(b["week"]).replace("2025_REG_w", "W").replace("2025_", ""))
        rows.append(f"""<tr>
          <td class="num muted">{wk}</td>
          <td>{_logo(b['away'], logos)} <span class="muted">@</span> {_logo(b['home'], logos)}</td>
          <td>{_logo(b['pick'], logos)} <b>{html.escape(b['pick'])}</b></td>
          <td class="num">{b['model_prob'] * 100:.0f}%</td>
          <td class="num">{b['market_prob'] * 100:.0f}%</td>
          <td class="num" style="color:#22D3EE">{b['edge'] * 100:+.0f}%</td>
          <td class="num">{b['decimal_odds']:.2f}</td>
          <td class="num">${b['stake']:.2f}</td>
          <td class="num" style="color:{rc}">{'GANÓ' if won else 'perdió'}</td>
          <td class="num" style="color:{rc}">${b['pnl']:+.2f}</td>
          <td class="num">${b['bankroll']:.2f}</td>
        </tr>""")
    body = "".join(rows)

    verdict = ("La estrategia fue rentable." if pos else
               "La estrategia perdió: el moneyline NFL es eficiente y el modelo "
               "TrueSkill (solo ratings) produce edges sobreconfiados. Necesita "
               "calibración de probabilidades o un threshold de edge más alto antes de operar live.")

    return f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Backtest NFL {res['season']}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {{ --bg:#0F1117; --surface:#1A1D27; --surface-alt:#22262F; --border:#2D3340;
    --text:#E2E8F0; --muted:#94A3B8; --cyan:#22D3EE; }}
  *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);
    font-family:Inter,system-ui,sans-serif;line-height:1.6;-webkit-font-smoothing:antialiased}}
  .wrap{{max-width:1080px;margin:0 auto;padding:48px 24px 64px}}
  .num{{font-family:'JetBrains Mono',ui-monospace,monospace}} .muted{{color:var(--muted)}}
  .eyebrow{{font-size:.75rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--cyan)}}
  h1{{font-size:2.25rem;font-weight:700;letter-spacing:-.015em;margin:.25rem 0 .25rem}}
  .sub{{color:var(--muted);font-size:.9rem;margin-bottom:24px}}
  .metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin:20px 0}}
  .metric{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;display:flex;flex-direction:column;gap:4px}}
  .m-label{{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}}
  .m-val{{font-size:1.4rem;font-weight:700}}
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;margin:16px 0}}
  .verdict{{border-left:none;background:var(--surface-alt);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin:16px 0;font-size:.95rem}}
  table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  th{{text-align:left;color:var(--muted);font-weight:600;font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;padding:8px;border-bottom:1px solid var(--border);position:sticky;top:0;background:var(--surface)}}
  td{{padding:7px 8px;border-bottom:1px solid var(--border)}}
  .scroll{{max-height:560px;overflow:auto;border-radius:12px;border:1px solid var(--border)}}
  footer{{margin-top:32px;color:var(--muted);font-size:.8rem;border-top:1px solid var(--border);padding-top:18px}}
</style></head><body><div class="wrap">
  <div class="eyebrow">Sports Quant Trading, NFL</div>
  <h1>Backtest NFL {res['season']}, TrueSkill + Kelly</h1>
  <div class="sub">Estrategia <b>{html.escape(res['strategy'])}</b>, bankroll inicial ${res['bankroll0']:.0f}, Kelly fraccional vs moneyline real (nflverse)</div>
  <div class="metrics">{metrics}</div>
  <div class="card"><div class="eyebrow" style="margin-bottom:10px">Curva de bankroll ({res['n_bets']} apuestas)</div>{_curve_svg(res['curve'], res['bankroll0'])}</div>
  <div class="verdict">{verdict}</div>
  <div class="scroll"><table>
    <thead><tr><th>Sem</th><th>Partido</th><th>Pick</th><th>Modelo</th><th>Mercado</th><th>Edge</th><th>Cuota</th><th>Stake</th><th>Resultado</th><th>PnL</th><th>Bankroll</th></tr></thead>
    <tbody>{body}</tbody>
  </table></div>
  <footer>Backtest predict-then-update (el modelo solo ve juegos previos). TrueSkill ignora margen, localía e lesiones. No es consejo financiero.</footer>
</div></body></html>"""
