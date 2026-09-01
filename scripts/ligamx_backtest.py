#!/usr/bin/env python
"""Backtest Liga MX sobre football-data.co.uk (MEX.csv) — calibración + modelos + apuestas.

Tres partes (todas walk-forward, sin lookahead):
  A. CALIBRACIÓN de la ventaja de localía Elo: grid search minimizando Brier
     (score 1/0.5/0) replayando temporadas históricas.
  B. CALIDAD de modelos en 2025/26: Elo (Brier binario con empate=0.5) y
     Poisson 1X2 (Brier multiclase, fit con ventana expansiva, neutral=False),
     ambos comparados contra las cuotas de cierre promedio del mercado.
  C. SIMULACIÓN de apuestas 2025/26: Poisson 1X2 vs cuotas de cierre (AvgC*),
     apostando cuando EV = p×cuota − 1 ≥ umbral, sizing ¼ Kelly, bankroll 1000.

Fuente: data/liga_mx_2026/ingest/MEX.csv (descarga de football-data.co.uk/new/MEX.csv).
Los resultados van al finding docs/findings/2026-07-14-ligamx-backtest.md.

    python scripts/ligamx_backtest.py
"""
from __future__ import annotations

import csv
import math
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.console import enable_utf8

enable_utf8()

from adapters.football.strength_models import EloSystem
from adapters.football.poisson import PoissonGoalsModel
from adapters.football.trueskill import TrueSkillSystem

CSV = Path(__file__).resolve().parent.parent / "data" / "liga_mx_2026" / "ingest" / "MEX.csv"

# CSV de football-data → team_id del proyecto (los 18 del Apertura 2026 + mazatlan,
# que jugó hasta el Clausura 2026 y cedió su lugar a atlante).
TEAM_MAP = {
    "Club America": "america", "Guadalajara Chivas": "guadalajara",
    "Cruz Azul": "cruz_azul", "UNAM Pumas": "pumas_unam", "Tigres UANL": "tigres_uanl",
    "Monterrey": "monterrey", "Toluca": "toluca", "Pachuca": "pachuca",
    "Club Leon": "leon", "Atlas": "atlas", "Santos Laguna": "santos_laguna",
    "Juarez": "juarez", "Queretaro": "queretaro", "Atl. San Luis": "atletico_san_luis",
    "Club Tijuana": "tijuana", "Puebla": "puebla", "Necaxa": "necaxa",
    "Mazatlan FC": "mazatlan",
}


def slug(name: str) -> str:
    return TEAM_MAP.get(name) or re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def load_matches(seasons: set[str]) -> list[dict]:
    rows = []
    for r in csv.DictReader(open(CSV, encoding="utf-8-sig")):
        if r["Season"] not in seasons or not r["HG"] or not r["AG"]:
            continue
        rows.append({
            "date": datetime.strptime(r["Date"], "%d/%m/%Y"),
            "season": r["Season"],
            "home": slug(r["Home"]), "away": slug(r["Away"]),
            "hg": int(float(r["HG"])), "ag": int(float(r["AG"])),
            "oh": float(r["AvgCH"]) if r.get("AvgCH") else None,
            "od": float(r["AvgCD"]) if r.get("AvgCD") else None,
            "oa": float(r["AvgCA"]) if r.get("AvgCA") else None,
        })
    rows.sort(key=lambda m: m["date"])
    return rows


def elo_score(hg: int, ag: int) -> float:
    return 1.0 if hg > ag else (0.0 if hg < ag else 0.5)


# ── A. calibración de localía ────────────────────────────────────────────────

def calibrate_home_adv(matches: list[dict], burn_in: int) -> list[tuple[float, float]]:
    """[(home_adv, brier)] — replay Elo completo, scoring después del burn-in."""
    out = []
    for adv in range(0, 125, 5):
        elo = EloSystem(k=40.0, home_adv=float(adv))
        se = n = 0
        for i, m in enumerate(matches):
            if i >= burn_in:
                e = elo.expected_home(m["home"], m["away"])
                se += (e - elo_score(m["hg"], m["ag"])) ** 2
                n += 1
            elo.update_match(m["home"], m["away"], m["hg"], m["ag"])
        out.append((float(adv), se / n))
    return out


def torneo_corto(d) -> tuple[int, str]:
    """(año, 'A'|'C'): Jul-Dic = Apertura, Ene-Jun = Clausura."""
    return (d.year, "A" if d.month >= 7 else "C")


def calibrate_boundary_regression(matches: list[dict], burn_in: int,
                                  home_adv: float) -> list[tuple[float, float]]:
    """[(rho, brier)] — regresión parcial a la media en cada frontera de torneo
    corto. Los torneos cortos reinician la TABLA, no la fuerza: rho=1 (continuo)
    es subóptimo pero un reset fuerte (rho<=0.5) es peor."""
    out = []
    for rho in (1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.50):
        elo = EloSystem(k=40.0, home_adv=home_adv)
        se = n = 0
        cur = None
        for i, m in enumerate(matches):
            t = torneo_corto(m["date"])
            if cur is not None and t != cur:
                elo.ratings = {k: 1500.0 + rho * (v - 1500.0)
                               for k, v in elo.ratings.items()}
            cur = t
            if i >= burn_in:
                se += (elo.expected_home(m["home"], m["away"])
                       - elo_score(m["hg"], m["ag"])) ** 2
                n += 1
            elo.update_match(m["home"], m["away"], m["hg"], m["ag"])
        out.append((rho, se / n))
    return out


# ── B. calidad de modelos en la temporada objetivo ──────────────────────────

def market_probs(m: dict) -> tuple[float, float, float] | None:
    if not (m["oh"] and m["od"] and m["oa"]):
        return None
    ih, idr, ia = 1 / m["oh"], 1 / m["od"], 1 / m["oa"]
    s = ih + idr + ia
    return ih / s, idr / s, ia / s


def outcome_idx(hg: int, ag: int) -> int:
    return 0 if hg > ag else (2 if ag > hg else 1)


class SeasonTracker:
    """Estado compartido de B/C: regresión ρ en fronteras de torneo corto y
    conteo de apariciones por equipo POR TORNEO (para el warmup de N fechas)."""

    def __init__(self, elo: EloSystem, *, rho: float = 1.0, warmup: int = 0):
        self.elo = elo
        self.rho = rho
        self.warmup = warmup
        self._torneo = None
        self._played: dict[str, int] = {}

    def on_match_start(self, m: dict) -> bool:
        """Avanza fronteras y devuelve True si el partido CUENTA (pasó warmup)."""
        t = torneo_corto(m["date"])
        if self._torneo is not None and t != self._torneo:
            self.elo.ratings = {k: 1500.0 + self.rho * (v - 1500.0)
                                for k, v in self.elo.ratings.items()}
            self._played = {}  # el warmup es POR torneo corto
        self._torneo = t
        return (self._played.get(m["home"], 0) >= self.warmup
                and self._played.get(m["away"], 0) >= self.warmup)

    def on_match_end(self, m: dict) -> None:
        self._played[m["home"]] = self._played.get(m["home"], 0) + 1
        self._played[m["away"]] = self._played.get(m["away"], 0) + 1


def eval_models(history: list[dict], target: list[dict], home_adv: float,
                refit_every: int = 9, *, rho: float = 1.0, warmup: int = 0) -> dict:
    elo = EloSystem(k=40.0, home_adv=home_adv)
    tracker = SeasonTracker(elo, rho=rho, warmup=warmup)
    for m in history:
        tracker.on_match_start(m)
        elo.update_match(m["home"], m["away"], m["hg"], m["ag"])
        tracker.on_match_end(m)

    seen = [(m["home"], m["away"], m["hg"], m["ag"]) for m in history]
    poisson = PoissonGoalsModel(neutral=False).fit(seen)

    elo_se = mkt_bin_se = 0.0
    poi_se = mkt_se = 0.0
    poi_ll = mkt_ll = 0.0
    n = n3 = skipped = 0
    since_fit = 0
    for m in target:
        counts = tracker.on_match_start(m)
        mp = market_probs(m)
        if counts:
            # Elo binario (score 1/0.5/0) vs mercado en la misma métrica
            s = elo_score(m["hg"], m["ag"])
            elo_se += (elo.expected_home(m["home"], m["away"]) - s) ** 2
            n += 1
            if mp:
                mkt_bin_se += ((mp[0] + 0.5 * mp[1]) - s) ** 2
                # Poisson 1X2 multiclase vs mercado
                fc = poisson.forecast(m["home"], m["away"])
                pr = fc.prob_result()
                p3 = (pr["home"], pr["draw"], pr["away"])
                k = outcome_idx(m["hg"], m["ag"])
                poi_se += sum((p3[i] - (1 if i == k else 0)) ** 2 for i in range(3)) / 3
                mkt_se += sum((mp[i] - (1 if i == k else 0)) ** 2 for i in range(3)) / 3
                poi_ll += -math.log(max(p3[k], 1e-9))
                mkt_ll += -math.log(max(mp[k], 1e-9))
                n3 += 1
        else:
            skipped += 1
        # avanzar modelos (walk-forward) — el warmup no frena el aprendizaje
        elo.update_match(m["home"], m["away"], m["hg"], m["ag"])
        tracker.on_match_end(m)
        seen.append((m["home"], m["away"], m["hg"], m["ag"]))
        since_fit += 1
        if since_fit >= refit_every:
            poisson = PoissonGoalsModel(neutral=False).fit(seen)
            since_fit = 0
    return {
        "n": n, "n_odds": n3, "skipped_warmup": skipped,
        "elo_brier": elo_se / n, "market_brier_bin": mkt_bin_se / n3,
        "poisson_brier3": poi_se / n3, "market_brier3": mkt_se / n3,
        "poisson_logloss": poi_ll / n3, "market_logloss": mkt_ll / n3,
    }


# ── C. simulación de apuestas ────────────────────────────────────────────────

def bet_sim(history: list[dict], target: list[dict], *, ev_min: float,
            kelly_frac: float = 0.25, bankroll: float = 1000.0,
            max_bet: float = 25.0, refit_every: int = 9,
            rho: float = 1.0, warmup: int = 0) -> dict:
    seen = [(m["home"], m["away"], m["hg"], m["ag"]) for m in history]
    poisson = PoissonGoalsModel(neutral=False).fit(seen)
    tracker = SeasonTracker(EloSystem(), rho=rho, warmup=warmup)  # sólo fronteras/warmup
    for m in history:
        tracker.on_match_start(m)
        tracker.on_match_end(m)
    bank = bankroll
    peak = bank
    max_dd = 0.0
    nbets = wins = 0
    staked = 0.0
    since_fit = 0
    for m in target:
        counts = tracker.on_match_start(m)
        odds = (m["oh"], m["od"], m["oa"])
        if counts and all(odds):
            fc = poisson.forecast(m["home"], m["away"])
            pr = fc.prob_result()
            p3 = (pr["home"], pr["draw"], pr["away"])
            k_res = outcome_idx(m["hg"], m["ag"])
            best = max(range(3), key=lambda i: p3[i] * odds[i])
            ev = p3[best] * odds[best] - 1
            if ev >= ev_min:
                b = odds[best] - 1
                f = max(0.0, (p3[best] * b - (1 - p3[best])) / b) * kelly_frac
                stake = min(max_bet, f * bank)
                if stake >= 5:
                    nbets += 1
                    staked += stake
                    if best == k_res:
                        bank += stake * b
                        wins += 1
                    else:
                        bank -= stake
                    peak = max(peak, bank)
                    max_dd = max(max_dd, (peak - bank) / peak)
        tracker.on_match_end(m)
        seen.append((m["home"], m["away"], m["hg"], m["ag"]))
        since_fit += 1
        if since_fit >= refit_every:
            poisson = PoissonGoalsModel(neutral=False).fit(seen)
            since_fit = 0
    return {"ev_min": ev_min, "n_bets": nbets, "wins": wins,
            "staked": staked, "pnl": bank - bankroll,
            "roi_staked": (bank - bankroll) / staked if staked else 0.0,
            "final": bank, "max_dd": max_dd}


def trueskill_trajectory(history: list[dict], target: list[dict],
                         home_adv: float, *, rho: float = 0.80) -> dict[str, list[float]]:
    """{team: [mu tras cada fecha jugada]} durante la temporada objetivo.

    TrueSkill se siembra desde el Elo al inicio de la temporada objetivo (replay
    de history con regresión ρ en fronteras) y evoluciona partido a partido.
    El índice de la lista es la fecha (jornada) del EQUIPO (1..n).
    """
    elo = EloSystem(k=40.0, home_adv=home_adv)
    tracker = SeasonTracker(elo, rho=rho)
    for m in history:
        tracker.on_match_start(m)
        elo.update_match(m["home"], m["away"], m["hg"], m["ag"])
        tracker.on_match_end(m)
    # frontera history→target (nueva temporada corta)
    seed = {k: 1500.0 + rho * (v - 1500.0) for k, v in elo.ratings.items()}

    ts = TrueSkillSystem()
    ts.seed_from_elo(seed)
    teams = {m["home"] for m in target} | {m["away"] for m in target}
    traj: dict[str, list[float]] = {t: [ts.ratings[t].mu if t in ts.ratings else 25.0]
                                    for t in teams}
    for m in target:
        ts.update_match(m["home"], m["away"], m["hg"], m["ag"])
        for side in (m["home"], m["away"]):
            traj[side].append(ts.ratings[side].mu)
    return traj


def market_implied_trajectory(target: list[dict]) -> dict[str, list[float]]:
    """{team: [P(win) implícita del mercado en cada fecha jugada]} en la temporada.

    Cuotas de cierre promedio, normalizadas sin vig (misma normalización que
    market_probs). Es la vista 'qué pensaba el mercado de cada equipo', análoga
    a la trayectoria TrueSkill (que es 'qué pensaba el modelo')."""
    traj: dict[str, list[float]] = {}
    for m in target:
        mp = market_probs(m)
        if mp is None:
            continue
        traj.setdefault(m["home"], []).append(mp[0])
        traj.setdefault(m["away"], []).append(mp[2])
    return traj


def main() -> None:
    cal_matches = load_matches({"2022/2023", "2023/2024", "2024/2025", "2025/2026"})
    burn = sum(1 for m in cal_matches if m["season"] == "2022/2023")
    print(f"=== A. Calibración localía (replay {len(cal_matches)} partidos, "
          f"burn-in {burn}) ===")
    grid = calibrate_home_adv(cal_matches, burn)
    best_adv, best_brier = min(grid, key=lambda t: t[1])
    for adv, brier in grid:
        mark = "  <-- óptimo" if adv == best_adv else ""
        if adv % 20 == 0 or adv == best_adv:
            print(f"  home_adv={adv:5.0f}  brier={brier:.5f}{mark}")

    print(f"\n=== A2. Regresión a la media en fronteras Apertura/Clausura "
          f"(home_adv={best_adv:.0f}) ===")
    for rho, brier in calibrate_boundary_regression(cal_matches, burn, best_adv):
        note = "  (continuo)" if rho == 1.0 else ("  <-- usado en seeds" if rho == 0.80 else "")
        print(f"  rho={rho:.2f}  brier={brier:.5f}{note}")

    history = load_matches({"2023/2024", "2024/2025"})
    target = load_matches({"2025/2026"})
    RHO, WARMUP = 0.80, 3  # producción: regresión 20% en fronteras + warmup 3 fechas
    print(f"\n=== B. Modelos en 2025/26 (walk-forward; historia {len(history)}, "
          f"objetivo {len(target)}; rho={RHO}, warmup={WARMUP} fechas) ===")
    q = eval_models(history, target, best_adv, rho=RHO, warmup=WARMUP)
    print(f"  (excluidos por warmup: {q['skipped_warmup']} partidos)")
    print(f"  Elo (binario 1/0.5/0):  brier={q['elo_brier']:.5f}   "
          f"mercado={q['market_brier_bin']:.5f}")
    print(f"  Poisson 1X2 (3-clases): brier={q['poisson_brier3']:.5f}   "
          f"mercado={q['market_brier3']:.5f}")
    print(f"  Poisson log-loss={q['poisson_logloss']:.4f}   "
          f"mercado={q['market_logloss']:.4f}   (n={q['n_odds']})")

    print(f"\n=== C. Apuestas Poisson vs cuotas de CIERRE 2025/26 "
          f"(¼ Kelly, max $25; rho={RHO}, warmup={WARMUP} fechas) ===")
    for ev_min in (0.02, 0.05, 0.10, 0.15):
        r = bet_sim(history, target, ev_min=ev_min, rho=RHO, warmup=WARMUP)
        print(f"  EV>={ev_min:.2f}: {r['n_bets']:3d} apuestas ({r['wins']}W)  "
              f"staked=${r['staked']:7.2f}  PnL=${r['pnl']:+8.2f}  "
              f"ROI/staked={r['roi_staked']:+.1%}  maxDD={r['max_dd']:.1%}")


if __name__ == "__main__":
    main()
