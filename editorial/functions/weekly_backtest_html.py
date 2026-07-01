"""Reporte HTML semana-a-semana de un backtest NFL, con logos y comentarios.

Design system pypro.mx (dark). Recibe el dict de simulate_combo(collect_bets=True),
un mapa {team_code: data_uri} de logos, y un label de config. Función pura.
"""
from __future__ import annotations

import html
from collections import defaultdict
from typing import Any


def _logo(code: str, logos: dict[str, str], size: int = 20) -> str:
    uri = logos.get(code)
    if uri:
        return f'<img src="{uri}" width="{size}" height="{size}" style="vertical-align:middle;border-radius:4px" alt="{html.escape(code)}">'
    return f'<span class="num">{html.escape(code)}</span>'


def _week_comment(w: int, wins: int, losses: int, pnl: float) -> str:
    rec = f"{wins}-{losses}"
    if pnl > 0 and wins > losses:
        return f"Semana ganadora ({rec}), +${pnl:.0f}."
    if pnl > 0:
        return f"Verde por pocas pero buenas cuotas ({rec}), +${pnl:.0f}."
    if pnl < 0 and losses > wins:
        return f"Mala semana ({rec}), {pnl:+.0f}."
    return f"Plana ({rec}), {pnl:+.0f}."


def _overall_comment(res: dict, weeks: dict) -> str:
    n, wr, roi = res["n_bets"], res["win_rate"] * 100, res["roi"] * 100
    bf, b0 = res["bankroll_final"], res["bankroll0"]
    best = max(weeks.items(), key=lambda kv: kv[1]["pnl"], default=(0, {"pnl": 0}))
    worst = min(weeks.items(), key=lambda kv: kv[1]["pnl"], default=(0, {"pnl": 0}))
    sign = "ganó" if roi >= 0 else "perdió"
    return (f"En {res['season']} esta config {sign} ({roi:+.1f}% ROI): bankroll "
            f"${b0:.0f} → ${bf:.0f} en {n} apuestas, {wr:.0f}% de acierto. "
            f"Mejor semana: W{best[0]} ({best[1]['pnl']:+.0f}); peor: W{worst[0]} ({worst[1]['pnl']:+.0f}). "
            f"OJO: es UNA temporada. La misma estrategia pierde fuerte en otros años "
            f"(ver la matriz de 32 escenarios). Un buen año es varianza, no edge.")


def _group_weeks(res: dict) -> dict[int, dict]:
    weeks: dict[int, dict] = defaultdict(lambda: {"bets": [], "pnl": 0.0, "w": 0, "l": 0})
    for b in res["bets"]:
        wk = weeks[b["week"]]
        wk["bets"].append(b)
        wk["pnl"] += b["pnl"]
        wk["w"] += b["won"]
        wk["l"] += not b["won"]
    return weeks


def render_week_sections(res: dict, logos: dict[str, str]) -> str:
    """Devuelve el HTML de las secciones semana-a-semana (reutilizable)."""
    weeks = _group_weeks(res)
    sections = ""
    for w in sorted(weeks):
        wk = weeks[w]
        pc = "#10B981" if wk["pnl"] >= 0 else "#EF4444"
        rows = ""
        for b in wk["bets"]:
            rc = "#10B981" if b["won"] else "#EF4444"
            dog = '<span class="tag">DOG</span>' if b.get("is_dog") else '<span class="tag fav">FAV</span>'
            rows += (f'<tr><td>{_logo(b["away"], logos)} <span class="muted">@</span> {_logo(b["home"], logos)}</td>'
                     f'<td>{_logo(b["pick"], logos)} <b>{html.escape(b["pick"])}</b> {dog}</td>'
                     f'<td class="num">{b["model_prob"] * 100:.0f}%</td>'
                     f'<td class="num">{b["market_prob"] * 100:.0f}%</td>'
                     f'<td class="num" style="color:#22D3EE">{b["edge"] * 100:+.0f}%</td>'
                     f'<td class="num">{b["decimal_odds"]:.2f}</td>'
                     f'<td class="num">${b["stake"]:.0f}</td>'
                     f'<td class="num" style="color:{rc}">{"GANO" if b["won"] else "perdio"}</td>'
                     f'<td class="num" style="color:{rc}">{b["pnl"]:+.0f}</td>'
                     f'<td class="num">${b["bankroll"]:.0f}</td></tr>')
        sections += (f'<section class="wk"><div class="wk-h"><h3>Semana {w}</h3>'
                     f'<span class="wk-pnl num" style="color:{pc}">{wk["pnl"]:+.0f}</span></div>'
                     f'<div class="comment">{_week_comment(w, wk["w"], wk["l"], wk["pnl"])}</div>'
                     f'<table><thead><tr><th>Partido</th><th>Pick</th><th>Mod</th><th>Mkt</th>'
                     f'<th>Edge</th><th>Cuota</th><th>Stake</th><th>Res</th><th>PnL</th><th>Bank</th></tr></thead>'
                     f'<tbody>{rows}</tbody></table></section>')
    return sections


def build_weekly_html(res: dict, logos: dict[str, str], config: dict[str, Any]) -> str:
    weeks = _group_weeks(res)
    sections = render_week_sections(res, logos)
    cfg = " · ".join(f"{k}: <b>{html.escape(str(v))}</b>" for k, v in config.items())
    roi = res["roi"] * 100
    rcol = "#10B981" if roi >= 0 else "#EF4444"
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Backtest semanal NFL {res['season']}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
 :root{{--bg:#0F1117;--surface:#1A1D27;--surface-alt:#22262F;--border:#2D3340;--text:#E2E8F0;--muted:#94A3B8;--cyan:#22D3EE}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,sans-serif;line-height:1.55}}
 .wrap{{max-width:1000px;margin:0 auto;padding:44px 22px 64px}}
 .num{{font-family:'JetBrains Mono',monospace}} .muted{{color:var(--muted)}}
 .eyebrow{{font-size:.75rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--cyan)}}
 h1{{font-size:2rem;font-weight:700;letter-spacing:-.015em;margin:.25rem 0}}
 .cfg{{color:var(--muted);font-size:.85rem;margin-bottom:14px}}
 .roi{{font-size:1.5rem;font-weight:700}}
 .intro{{background:var(--surface-alt);border:1px solid var(--border);border-radius:12px;padding:16px 18px;margin:16px 0 26px;font-size:.92rem}}
 section.wk{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin:14px 0}}
 .wk-h{{display:flex;align-items:center;justify-content:space-between}} .wk-h h3{{margin:0;font-size:1.1rem}}
 .wk-pnl{{font-weight:700}}
 .comment{{color:var(--muted);font-size:.82rem;margin:4px 0 10px}}
 table{{width:100%;border-collapse:collapse;font-size:.78rem}}
 th{{text-align:left;color:var(--muted);font-weight:600;font-size:.66rem;text-transform:uppercase;letter-spacing:.03em;padding:6px;border-bottom:1px solid var(--border)}}
 td{{padding:5px 6px;border-bottom:1px solid var(--border)}}
 .tag{{font-size:.6rem;font-weight:700;background:rgba(34,211,238,.15);color:#22D3EE;border-radius:4px;padding:1px 5px;margin-left:4px}}
 .tag.fav{{background:rgba(148,163,184,.15);color:#94A3B8}}
 footer{{margin-top:28px;color:var(--muted);font-size:.78rem;border-top:1px solid var(--border);padding-top:16px}}
</style></head><body><div class="wrap">
 <div class="eyebrow">Sports Quant Trading, NFL</div>
 <h1>Backtest semana a semana, {res['season']}</h1>
 <div class="cfg">{cfg}</div>
 <div class="roi" style="color:{rcol}">ROI {roi:+.1f}%  ·  yield {res['yield'] * 100:+.1f}%  ·  {res['n_bets']} apuestas  ·  {res['win_rate'] * 100:.0f}% acierto</div>
 <div class="intro">{_overall_comment(res, weeks)}</div>
 {sections}
 <footer>Predict-then-update (el modelo solo ve juegos previos de la temporada). FAV/DOG = favorito o underdog del mercado. No es consejo financiero.</footer>
</div></body></html>"""


def build_multi_weekly_html(strategies: list[dict], logos: dict[str, str],
                            season: int) -> str:
    """Reporte combinado: tabla resumen + secciones colapsables semana-a-semana por
    estrategia. `strategies` = [{label, res}] (res de simulate_combo collect_bets)."""
    strategies = sorted(strategies, key=lambda s: s["res"]["roi"], reverse=True)

    sumrows = ""
    for s in strategies:
        r = s["res"]
        c = "#10B981" if r["roi"] >= 0 else "#EF4444"
        sumrows += (f'<tr><td>{html.escape(s["label"])}</td>'
                    f'<td class="num">{r["n_bets"]}</td>'
                    f'<td class="num">{r["win_rate"] * 100:.0f}%</td>'
                    f'<td class="num" style="color:{c};font-weight:700">{r["roi"] * 100:+.1f}%</td>'
                    f'<td class="num">{r["yield"] * 100:+.1f}%</td>'
                    f'<td class="num muted">${r["max_drawdown"]:.0f}</td></tr>')

    blocks = ""
    for s in strategies:
        r = s["res"]
        c = "#10B981" if r["roi"] >= 0 else "#EF4444"
        weeks = _group_weeks(r)
        blocks += (f'<details><summary><b>{html.escape(s["label"])}</b> '
                   f'<span class="num" style="color:{c}">ROI {r["roi"] * 100:+.1f}%</span> '
                   f'<span class="muted num">· {r["n_bets"]} apuestas · {r["win_rate"] * 100:.0f}%</span></summary>'
                   f'<div class="comment" style="margin:8px 0 12px">{_overall_comment(r, weeks)}</div>'
                   f'{render_week_sections(r, logos)}</details>')

    pos = sum(1 for s in strategies if s["res"]["roi"] > 0)
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Backtest NFL {season}, todas las estrategias</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
 :root{{--bg:#0F1117;--surface:#1A1D27;--surface-alt:#22262F;--border:#2D3340;--text:#E2E8F0;--muted:#94A3B8;--cyan:#22D3EE}}
 *{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,sans-serif;line-height:1.5}}
 .wrap{{max-width:1000px;margin:0 auto;padding:44px 22px 64px}}
 .num{{font-family:'JetBrains Mono',monospace}} .muted{{color:var(--muted)}}
 .eyebrow{{font-size:.75rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--cyan)}}
 h1{{font-size:2rem;font-weight:700;letter-spacing:-.015em;margin:.25rem 0}}
 .sub{{color:var(--muted);font-size:.88rem;margin-bottom:18px}}
 table{{width:100%;border-collapse:collapse;font-size:.8rem}}
 th{{text-align:left;color:var(--muted);font-weight:600;font-size:.66rem;text-transform:uppercase;letter-spacing:.03em;padding:7px;border-bottom:1px solid var(--border)}}
 td{{padding:6px 7px;border-bottom:1px solid var(--border)}}
 .summary-card{{border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:22px}}
 details{{background:var(--surface);border:1px solid var(--border);border-radius:12px;margin:10px 0;padding:6px 14px}}
 summary{{cursor:pointer;padding:8px 0;font-size:1rem}}
 .comment{{color:var(--muted);font-size:.82rem}}
 section.wk{{background:var(--surface-alt);border:1px solid var(--border);border-radius:10px;padding:12px 14px;margin:10px 0}}
 .wk-h{{display:flex;align-items:center;justify-content:space-between}} .wk-h h3{{margin:0;font-size:1rem}}
 .wk-pnl{{font-weight:700}} .tag{{font-size:.6rem;font-weight:700;background:rgba(34,211,238,.15);color:#22D3EE;border-radius:4px;padding:1px 5px;margin-left:4px}}
 .tag.fav{{background:rgba(148,163,184,.15);color:#94A3B8}}
 footer{{margin-top:28px;color:var(--muted);font-size:.78rem;border-top:1px solid var(--border);padding-top:16px}}
</style></head><body><div class="wrap">
 <div class="eyebrow">Sports Quant Trading, NFL</div>
 <h1>Backtest {season}, todas las estrategias</h1>
 <div class="sub">{len(strategies)} estrategias (modelo x lado), Kelly 0.4, reset por temporada. {pos}/{len(strategies)} positivas en {season}. Expandi cada una para el detalle semana a semana.</div>
 <div class="summary-card"><table><thead><tr><th>Estrategia</th><th>Apuestas</th><th>Win%</th><th>ROI</th><th>Yield</th><th>Max DD</th></tr></thead><tbody>{sumrows}</tbody></table></div>
 {blocks}
 <footer>Una sola temporada: positivo/negativo aca es VARIANZA, no edge (la misma estrategia voltea de signo entre anios). Ver matriz de 32 escenarios. No es consejo financiero.</footer>
</div></body></html>"""
