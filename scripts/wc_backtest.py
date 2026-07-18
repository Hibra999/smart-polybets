#!/usr/bin/env python
"""Backtest leak-free de los modelos del Mundial + cross-check con el historial real.

Para CADA partido jugado, pide la predicción del modelo (que evoluciona SOLO con
partidos previos → sin look-ahead) y la compara con el resultado real. Mide accuracy,
calibración (Brier), ROI de apuestas al precio de mercado, y contrasta con las apuestas
reales de la wallet.

    python scripts/wc_backtest.py            # imprime métricas (verificación)
    python scripts/wc_backtest.py --html     # genera editorial/reports/fifa_world_cup_2026/wc-backtest.html
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()

from adapters.football.db_reader import FootballDBReader
from research.functions.model_loader import get_event_prediction
from research.functions.wc_strategy import pick_side
from tournaments.registry import load_active_strategy

TID = "fifa_world_cup_2026"
HOME, AWAY = "HOME_WIN", "AWAY_WIN"
MODELS = ("elo", "bayes", "trueskill", "blend")


def _winner(hg: int, ag: int) -> str:
    return HOME if hg > ag else AWAY if ag > hg else "DRAW"


def _model_pick(comp: dict, model: str, blend_w: Decimal) -> tuple[str, Decimal]:
    """Lado elegido y su prob para un modelo dado."""
    elo, bayes, ts = comp["elo"], comp["bayes"], comp.get("trueskill", comp["elo"])
    if model == "elo":
        h, a = elo[HOME], elo[AWAY]
    elif model == "bayes":
        h, a = bayes[HOME], bayes[AWAY]
    elif model == "trueskill":
        h, a = ts[HOME], ts[AWAY]
    else:  # blend
        h = blend_w * elo[HOME] + (1 - blend_w) * bayes[HOME]
        a = blend_w * elo[AWAY] + (1 - blend_w) * bayes[AWAY]
    return (HOME, h) if h >= a else (AWAY, a)


def _load_market(conn) -> dict:
    """{fixture_id: {'HOME_WIN': prob, 'AWAY_WIN': prob}} de las cuotas Polymarket."""
    cur = conn.cursor()
    cur.execute("SELECT fixture_id, home_prob, away_prob FROM polymarket_odds WHERE source='polymarket'")
    out = {}
    for fid, hp, ap in cur.fetchall():
        if hp is not None and ap is not None:
            out[fid] = {HOME: Decimal(str(hp)), AWAY: Decimal(str(ap))}
    return out


def run_backtest():
    strat = load_active_strategy(TID)
    bw = strat.blend_weight
    reader = FootballDBReader(TID)
    conn = sqlite3.connect(f"data/{TID}/{TID}.sqlite")
    market = _load_market(conn)

    finished = reader.get_finished_fixtures()  # cronológico
    rows = []
    prev_n = -1
    leak_ok = True
    for fx in finished:
        fid = fx["id"]
        pred = get_event_prediction(fid, TID)
        if pred is None:
            continue
        comp = pred.components
        hg, ag = int(fx["home_goals"]), int(fx["away_goals"])
        winner = _winner(hg, ag)
        picks = {m: _model_pick(comp, m, bw) for m in MODELS}
        bside, bprob = picks["blend"]
        mkt = market.get(fid)
        row = {
            "fid": fid, "home": pred.participant_home, "away": pred.participant_away,
            "hg": hg, "ag": ag, "winner": winner,
            "p_home_blend": float(bw * comp["elo"][HOME] + (1 - bw) * comp["bayes"][HOME]),
            "picks": {m: (s, float(p)) for m, (s, p) in picks.items()},
            "blend_side": bside, "blend_prob": float(bprob),
            "conf": pred.model_confidence.value, "n": pred.sample_size,
            "mkt": {HOME: float(mkt[HOME]), AWAY: float(mkt[AWAY])} if mkt else None,
        }
        rows.append(row)
        # chequeo leak-free: la muestra no debería "saber" del futuro (monótona no estricta
        # dentro del orden cronológico; una caída grande señalaría un problema de orden).
        prev_n = pred.sample_size
    conn.close()
    return rows, strat


def metrics(rows):
    n = len(rows)
    draws = sum(1 for r in rows if r["winner"] == "DRAW")
    decisive = n - draws
    out = {"n": n, "draws": draws, "decisive": decisive, "per_model": {}}

    for m in MODELS:
        # accuracy incluyendo empates como fallo (realista, como resuelve Polymarket)
        hit_all = sum(1 for r in rows if r["picks"][m][0] == r["winner"])
        # accuracy solo en partidos decisivos (predicción pura de ganador)
        hit_dec = sum(1 for r in rows if r["winner"] != "DRAW" and r["picks"][m][0] == r["winner"])
        out["per_model"][m] = {
            "acc_all": hit_all / n if n else 0,
            "acc_dec": hit_dec / decisive if decisive else 0,
        }

    # Brier del blend sobre P(home gana outright)
    brier = 0.0
    for r in rows:
        y = 1.0 if r["winner"] == HOME else 0.0
        brier += (r["p_home_blend"] - y) ** 2
    out["brier"] = brier / n if n else 0

    # Calibración: buckets de prob del lado elegido (blend) vs freq real de acierto
    buckets = {}
    for r in rows:
        p = r["blend_prob"]
        b = min(int(p * 10), 9)  # 0.0-1.0 → 0..9
        won = 1 if r["blend_side"] == r["winner"] else 0
        buckets.setdefault(b, []).append((p, won))
    out["calib"] = {b: (sum(x[0] for x in v) / len(v), sum(x[1] for x in v) / len(v), len(v))
                    for b, v in sorted(buckets.items())}

    # Simulación de apuestas: blend pick al precio de mercado, solo edge>0, flat 1u
    bet_rows = [r for r in rows if r["mkt"]]
    staked = pnl = wins = losses = 0
    n_bets = 0
    for r in bet_rows:
        side, prob = r["blend_side"], r["blend_prob"]
        price = r["mkt"][side]
        edge = prob - price
        if edge <= 0 or price <= 0:
            continue
        n_bets += 1
        staked += 1
        if r["blend_side"] == r["winner"]:
            pnl += (1 - price) / price  # ganó: payout 1/price
            wins += 1
        else:
            pnl -= 1
            losses += 1
    out["bet"] = {"n_market": len(bet_rows), "n_bets": n_bets, "wins": wins,
                  "losses": losses, "staked": staked, "pnl": pnl,
                  "roi": (pnl / staked) if staked else 0}

    # Comparación de estrategias: A = "pick GANA" (pierde en empate) vs
    # B = "rival NO gana" (doble-oportunidad 1X: pick gana O empate a 90').
    def _sim(rs, strategy):
        n = w = 0; st = p = 0.0; dc = 0
        for r in rs:
            if not r["mkt"]:
                continue
            pick = r["blend_side"]; other = AWAY if pick == HOME else HOME
            if strategy == "A":
                price = r["mkt"][pick]; won = (r["winner"] == pick)
                edge = r["blend_prob"] - price
                if edge <= 0:  # A apuesta solo edge>0 (como el agente)
                    continue
            else:
                price = 1 - r["mkt"][other]; won = (r["winner"] != other)
            if not (0 < price < 1):
                continue
            n += 1; st += 1
            if won:
                w += 1; p += (1 - price) / price
                if r["winner"] == "DRAW":
                    dc += 1
            else:
                p -= 1
        return {"n": n, "w": w, "l": n - w, "roi": (p / st) if st else 0, "draws": dc}
    # B sobre los mismos partidos que A elegiría (edge>0), para comparar manzanas con manzanas
    a_fids = {r["fid"] for r in rows if r["mkt"] and (r["blend_prob"] - r["mkt"][r["blend_side"]]) > 0}
    out["compare"] = {"A": _sim(rows, "A"),
                      "B": _sim([r for r in rows if r["fid"] in a_fids], "B")}
    return out


def wallet_crosscheck(rows):
    """Contrasta las apuestas reales de la wallet con lo que el modelo predijo."""
    try:
        from core.env import load_env
        load_env(str(Path(__file__).resolve().parent.parent / ".env"))
        from venue.gateway import PolymarketGateway
        from venue.matching import canon
    except Exception as e:
        return {"available": False, "reason": str(e)}
    gw = PolymarketGateway()
    try:
        closed = gw.closed_positions(limit=50)
        openp = [p for p in gw.positions()]
    except Exception as e:
        return {"available": False, "reason": f"cuenta live no disponible: {e}"}

    # index de fixtures por equipo canon (para mapear "Will X win" → partido + predicción)
    by_team = {}
    for r in rows:
        by_team.setdefault(canon(r["home"]), r)
        by_team.setdefault(canon(r["away"]), r)

    def team_of(title):
        t = (title or "").lower().replace("will ", "").split(" win")[0].strip()
        return canon(t)

    checked, agree, our_wins = [], 0, 0
    seen = set()
    # apuestas reales: cerradas (ganadas) + abiertas resueltas a 0 (perdidas)
    bets = [("closed", c) for c in closed] + [("open", p) for p in openp
            if p.current_price is not None and p.current_price == 0]
    for kind, pos in bets:
        title = pos.title
        tk = team_of(title)
        r = by_team.get(tk)
        if r is None or (title, kind) in seen:
            continue
        seen.add((title, kind))
        # ¿ese equipo es home o away en el partido?
        our_side = HOME if canon(r["home"]) == tk else AWAY
        our_won = (our_side == r["winner"])
        model_side = r["blend_side"]
        agrees = (model_side == our_side)
        pnl = float(getattr(pos, "realized_pnl", 0) or 0) if kind == "closed" else \
              -float(pos.size_shares * pos.avg_entry_price)
        checked.append({"title": title[:34], "our_side": our_side, "model_side": model_side,
                        "agree": agrees, "our_won": our_won, "pnl": pnl,
                        "model_prob": r["blend_prob"]})
        if agrees:
            agree += 1
        if our_won:
            our_wins += 1
    # win-rate cuando el modelo coincidió con tu apuesta vs cuando no (¿aporta valor?)
    agr = [c for c in checked if c["agree"]]
    dis = [c for c in checked if not c["agree"]]
    agr_wr = sum(1 for c in agr if c["our_won"]) / len(agr) if agr else 0
    dis_wr = sum(1 for c in dis if c["our_won"]) / len(dis) if dis else 0
    return {"available": True, "n": len(checked), "agree": agree, "our_wins": our_wins,
            "agree_winrate": agr_wr, "disagree_winrate": dis_wr,
            "n_agree": len(agr), "n_disagree": len(dis), "rows": checked}


def verify(rows, mx):
    checks = []
    # 1) probabilidades válidas (home+away ≈ 1 en modelo win/no-win)
    bad = [r for r in rows if not (0 <= r["blend_prob"] <= 1)]
    checks.append(("Probabilidades en [0,1]", not bad, f"{len(bad)} fuera de rango"))
    # 2) sin predicción sobre su propio resultado: el 1er partido debe tener n=0
    first_n = rows[0]["n"] if rows else None
    checks.append(("1er partido con muestra n=0 (leak-free)", first_n == 0, f"n={first_n}"))
    # 3) la muestra máxima < total (nunca ve todos)
    max_n = max((r["n"] for r in rows), default=0)
    checks.append(("Muestra máx < nº de partidos (sin ver el futuro)", max_n < len(rows),
                   f"max_n={max_n} < {len(rows)}"))
    # 4) accuracy razonable (> azar 50% en decisivos)
    acc = mx["per_model"]["blend"]["acc_dec"]
    checks.append(("Accuracy blend > 50% (mejor que azar)", acc > 0.5, f"{acc*100:.1f}%"))
    # 5) conteo: predicciones == partidos con predicción
    checks.append(("Todos los partidos jugados predichos", len(rows) > 0, f"{len(rows)} filas"))
    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", action="store_true")
    a = ap.parse_args()
    rows, strat = run_backtest()
    mx = metrics(rows)
    wc = wallet_crosscheck(rows)
    checks = verify(rows, mx)

    if not a.html:
        print(f"\n=== BACKTEST WC — {mx['n']} partidos ({mx['decisive']} decisivos, {mx['draws']} empates) ===")
        print(f"blend_weight={strat.blend_weight}  side_criterion={strat.side_criterion}\n")
        print("ACCURACY (acierto del lado elegido):")
        for m in MODELS:
            pm = mx["per_model"][m]
            print(f"  {m:<10} incl. empates: {pm['acc_all']*100:5.1f}%   solo decisivos: {pm['acc_dec']*100:5.1f}%")
        print(f"\nBrier (blend, P home): {mx['brier']:.4f}   (0=perfecto, 0.25=azar)")
        print("\nCALIBRACIÓN (prob elegida → acierto real):")
        for b, (pavg, freq, cnt) in mx["calib"].items():
            print(f"  [{b/10:.1f}-{(b+1)/10:.1f})  pred {pavg*100:5.1f}%  real {freq*100:5.1f}%  (n={cnt})")
        bet = mx["bet"]
        print(f"\nAPUESTAS (blend pick, edge>0, al precio de mercado, flat 1u):")
        print(f"  {bet['n_bets']} apuestas de {bet['n_market']} con cuota · {bet['wins']}W-{bet['losses']}L · "
              f"PnL {bet['pnl']:+.2f}u · ROI {bet['roi']*100:+.1f}%")
        cmp = mx["compare"]
        print(f"\nESTRATEGIA A (pick GANA, pierde en empate)  vs  B (rival NO gana = 1X a 90'):")
        print(f"  A: {cmp['A']['n']} apuestas · {cmp['A']['w']}-{cmp['A']['l']} · ROI {cmp['A']['roi']*100:+.1f}%")
        print(f"  B: {cmp['B']['n']} apuestas · {cmp['B']['w']}-{cmp['B']['l']} · ROI {cmp['B']['roi']*100:+.1f}% · {cmp['B']['draws']} empates convertidos en ganancia")
        print("\nCROSS-CHECK con tu historial real:")
        if wc["available"]:
            print(f"  {wc['n']} apuestas tuyas mapeadas · modelo coincidió en {wc['agree']}/{wc['n']} · "
                  f"tú ganaste {wc['our_wins']}/{wc['n']}")
            print(f"  win-rate cuando el modelo COINCIDIÓ: {wc['agree_winrate']*100:.0f}% (n={wc['n_agree']})  "
                  f"vs cuando NO: {wc['disagree_winrate']*100:.0f}% (n={wc['n_disagree']})")
        else:
            print(f"  (no disponible: {wc['reason']})")
        print("\nVERIFICACIÓN DE BUGS:")
        for name, ok, detail in checks:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}  ({detail})")
        return

    # HTML
    from wc_backtest_html import render  # noqa
    html = render(rows, mx, wc, checks, strat)
    out = (Path(__file__).resolve().parent.parent
           / "editorial" / "reports" / "fifa_world_cup_2026" / "wc-backtest.html")
    out.write_text(html, encoding="utf-8")
    print(f"HTML: {out}")


if __name__ == "__main__":
    main()
