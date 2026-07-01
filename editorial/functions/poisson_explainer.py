"""Explainer HTML de CÓMO funciona el modelo Poisson de goles (audiencia general).

Documento de scroll con el design system pypro.mx (dark, Operator Blue, cyan, Inter
+ JetBrains Mono). Explica la idea, los tres pasos (ataque/defensa -> goles
esperados -> probabilidades de mercado), el shrinkage, la correccion de sede neutral,
los datos, el resultado del backtest y los limites. Cada paso se ilustra con un
ejemplo real calculado por el modelo (no inventado).

Función pura: recibe el dict `example` (numeros del modelo) y `backtest` (skill).
"""
from __future__ import annotations

import html
from typing import Any


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _backtest_table(markets: dict[str, Any]) -> str:
    rows = ""
    for name, m in markets.items():
        bss = m["bss"]
        color = "#22D3EE" if bss > 0 else "#94A3B8"
        verdict = "tiene skill" if bss > 0 else "sin skill"
        rows += (f'<tr><td>{html.escape(name)}</td><td class="num">{m["n"]}</td>'
                 f'<td class="num">{_pct(m["base_rate"])}</td>'
                 f'<td class="num" style="color:{color};font-weight:700">{bss:+.3f}</td>'
                 f'<td style="color:{color}">{verdict}</td></tr>')
    return rows


def build_poisson_explainer(*, example: dict, backtest: dict, generated_at: str) -> str:
    e = example
    h, a = html.escape(e["home"]).title(), html.escape(e["away"]).title()
    bt = _backtest_table(backtest["markets"])
    n2 = backtest["markets"].get("Over 2.5", {}).get("n", 0)

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cómo funciona el modelo de goles</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
 :root{{--bg:#0F1117;--surface:#1A1D27;--surface-alt:#22262F;--border:#2D3340;
   --text:#E2E8F0;--muted:#94A3B8;--blue:#2563EB;--cyan:#22D3EE;--green:#10B981;--amber:#F59E0B}}
 *{{box-sizing:border-box}} html{{scroll-behavior:smooth}}
 body{{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,sans-serif;
   line-height:1.7;-webkit-font-smoothing:antialiased}}
 .num{{font-family:'JetBrains Mono',ui-monospace,monospace}} .muted{{color:var(--muted)}}
 .wrap{{max-width:820px;margin:0 auto;padding:56px 24px 80px}}
 .eyebrow{{font-size:.75rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--cyan)}}
 h1{{font-size:clamp(2.2rem,5vw,3.2rem);font-weight:900;letter-spacing:-.025em;line-height:1.05;margin:.4rem 0 .6rem}}
 .lead{{font-size:1.15rem;color:var(--muted);max-width:680px}}
 section{{margin-top:56px;scroll-margin-top:24px}}
 .step{{font-size:.78rem;font-weight:700;color:var(--blue);letter-spacing:.08em;text-transform:uppercase}}
 h2{{font-size:1.7rem;font-weight:800;letter-spacing:-.015em;margin:.3rem 0 .6rem}}
 p{{margin:.6rem 0}}
 .formula{{background:var(--surface);border:1px solid var(--border);border-radius:12px;
   padding:18px 22px;font-family:'JetBrains Mono',monospace;font-size:.95rem;margin:18px 0;
   overflow-x:auto;line-height:1.9}}
 .formula .v{{color:var(--cyan)}} .formula .c{{color:var(--muted)}}
 .ex{{border-left:3px solid var(--cyan);background:#22D3EE0c;border-radius:0 10px 10px 0;
   padding:14px 18px;margin:18px 0}}
 .ex .tag{{font-size:.7rem;font-weight:700;color:var(--cyan);text-transform:uppercase;letter-spacing:.06em}}
 .ex table{{width:100%;border-collapse:collapse;margin-top:8px;font-size:.9rem}}
 .ex td{{padding:4px 0}} .ex td:last-child{{text-align:right}}
 .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0}}
 .card{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px 18px}}
 .card .k{{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}
 .card .val{{font-size:1.6rem;font-weight:800;color:var(--cyan)}}
 table.data{{width:100%;border-collapse:collapse;font-size:.88rem;margin-top:8px}}
 table.data th{{text-align:left;color:var(--muted);font-weight:600;font-size:.68rem;text-transform:uppercase;
   letter-spacing:.04em;padding:8px;border-bottom:1px solid var(--border)}}
 table.data td{{padding:8px;border-bottom:1px solid var(--border)}}
 .tbl{{border:1px solid var(--border);border-radius:12px;overflow:hidden}}
 .pill{{display:inline-block;font-size:.72rem;color:var(--muted);background:var(--surface-alt);
   border:1px solid var(--border);border-radius:9999px;padding:4px 12px;margin:3px 4px 3px 0}}
 .warn{{border-left:3px solid var(--amber);background:#F59E0B0c;border-radius:0 10px 10px 0;padding:14px 18px;margin:18px 0}}
 .warn b{{color:var(--amber)}}
 footer{{margin-top:64px;color:var(--muted);font-size:.82rem;border-top:1px solid var(--border);padding-top:24px}}
 @media(max-width:560px){{.grid2{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">

 <div class="eyebrow">Sports Quant Trading, modelo complementario</div>
 <h1>Cómo funciona el modelo de goles</h1>
 <p class="lead">Un modelo aparte que no predice quién gana, sino cuántos goles se
 anotan. Eso abre apuestas de Over/Under, ambos anotan y marcador. Aquí está, paso
 a paso y sin matemática de más, cómo llega a sus números.</p>

 <section>
   <div class="step">La idea</div>
   <h2>Los goles llegan como gotas de lluvia</h2>
   <p>Un gol es un evento raro que puede pasar en cualquier minuto. Cuando algo así
   se repite a un ritmo promedio conocido, la estadística tiene una herramienta
   exacta para eso: la <b>distribución de Poisson</b>. Si sé que un equipo anota en
   promedio, digamos, 2 goles por partido, Poisson me dice la probabilidad de que
   anote 0, 1, 2, 3 o más. Todo el modelo se reduce a estimar bien ese promedio
   para cada lado y dejar que Poisson haga el resto.</p>
 </section>

 <section>
   <div class="step">Paso 1</div>
   <h2>Ataque y defensa de cada equipo</h2>
   <p>Primero mido qué tan goleador y qué tan frágil es cada equipo, comparado con
   el promedio del torneo. Dos números por equipo:</p>
   <div class="formula">
     <span class="v">ataque</span> = goles que anota por partido / promedio de la liga&nbsp;&nbsp;<span class="c">(&gt;1 anota más que la media)</span><br>
     <span class="v">defensa</span> = goles que recibe por partido / promedio de la liga&nbsp;&nbsp;<span class="c">(&gt;1 defiende peor)</span>
   </div>
   <div class="ex">
     <span class="tag">Ejemplo real, {h} vs {a}</span>
     <table>
       <tr><td>{h}: ataque {e['atk_h']} (anota más que la media), defensa {e['def_h']} (concede menos)</td><td class="num">{e['mh']} partidos</td></tr>
       <tr><td>{a}: ataque {e['atk_a']}, defensa {e['def_a']}</td><td class="num">{e['ma']} partidos</td></tr>
     </table>
   </div>
 </section>

 <section>
   <div class="step">Paso 2</div>
   <h2>Los goles esperados de este partido</h2>
   <p>El ataque de uno choca con la defensa del otro. Multiplico el promedio de la
   liga por el ataque del que ataca y por la defensa del que defiende:</p>
   <div class="formula">
     <span class="v">goles esperados local</span> = base x ataque(local) x defensa(visita)<br>
     <span class="v">goles esperados visita</span> = base x ataque(visita) x defensa(local)<br>
     <span class="c">base = {e['base']} goles/equipo/partido (promedio del torneo)</span>
   </div>
   <div class="grid2">
     <div class="card"><div class="k">{h}</div><div class="val num">{e['lh']}</div><div class="muted">goles esperados</div></div>
     <div class="card"><div class="k">{a}</div><div class="val num">{e['la']}</div><div class="muted">goles esperados</div></div>
   </div>
   <p class="muted">{e['base']} x {e['atk_h']} x {e['def_a']} = {e['lh']} para {h};
   total esperado del partido: <b class="num" style="color:var(--cyan)">{e['tot']}</b> goles.</p>
 </section>

 <section>
   <div class="step">Paso 3</div>
   <h2>De los goles esperados a las probabilidades</h2>
   <p>Con los dos promedios, Poisson da la probabilidad de cada marcador exacto
   (0-0, 1-0, 2-1, ...). Sumando las casillas correctas salen todos los mercados:</p>
   <div class="grid2">
     <div class="card"><div class="k">Over 2.5 goles</div><div class="val num">{_pct(e['over25'])}</div></div>
     <div class="card"><div class="k">Ambos anotan (BTTS)</div><div class="val num">{_pct(e['btts'])}</div></div>
   </div>
   <p><span class="pill">Over 2.5 = sumar todos los marcadores con 3+ goles</span>
   <span class="pill">BTTS = ambos &gt; 0</span>
   <span class="pill">1X2 = comparar goles local vs visita</span></p>
   <div class="ex">
     <span class="tag">Salida del modelo, {h} vs {a}</span>
     <table>
       <tr><td>1X2 por goles</td><td class="num">{h} {_pct(e['res']['home'])} / empate {_pct(e['res']['draw'])} / {a} {_pct(e['res']['away'])}</td></tr>
       <tr><td>Marcadores más probables</td><td class="num">{", ".join(f"{i}-{j} ({_pct(p)})" for i,j,p in e['tops'])}</td></tr>
       <tr><td>Confianza</td><td class="num">{html.escape(e['conf'])}</td></tr>
     </table>
   </div>
 </section>

 <section>
   <div class="step">Dato fino</div>
   <h2>Cuando hay pocos partidos, el modelo es humilde</h2>
   <p>Un Mundial tiene pocos partidos por equipo. Si juzgara a un equipo por un solo
   resultado, un 4-0 lo volvería "ofensivo" para siempre. Para evitarlo, las tasas
   se <b>encogen hacia el promedio</b> (shrinkage): con pocos partidos, el equipo se
   parece a la media de la liga; recién con más juegos se le permite despegarse. Por
   eso los equipos sin historial (debutantes) salen con confianza baja y números
   cercanos al promedio, en vez de exagerados.</p>
 </section>

 <section>
   <div class="step">Corrección</div>
   <h2>En el Mundial no hay ventaja de local</h2>
   <p>Los datos sugerían una "ventaja local" enorme (el equipo listado primero
   anotaba casi el doble). Pero el Mundial se juega en <b>cancha neutral</b>: ese
   sesgo no era la cancha, era que el equipo nombrado primero suele ser el más
   fuerte. Aplicarlo habría inflado los goles del primer equipo. El modelo lo
   detecta y reparte parejo, así invertir local y visita solo intercambia los
   números, sin regalarle goles a nadie.</p>
 </section>

 <section>
   <div class="step">Los datos</div>
   <h2>De dónde salen los promedios</h2>
   <p>El modelo se alimenta de partidos reales con goles: el Mundial de Qatar 2022
   completo (48 partidos) más los del Mundial 2026 ya jugados. Sobre eso ajusta el
   ataque y la defensa de {e['n_teams']} selecciones.</p>
   <p><span class="pill">Qatar 2022: 48 partidos</span>
   <span class="pill">2026 en curso: se suman al jugarse</span>
   <span class="pill">~2.77 goles por partido</span></p>
 </section>

 <section>
   <div class="step">La prueba</div>
   <h2>¿Le pega a la realidad?</h2>
   <p>Se backtesteó prediciendo cada partido solo con los anteriores y comparando
   contra el promedio simple. La métrica BSS mide cuánto le gana al promedio
   (positivo = aporta):</p>
   <div class="tbl"><table class="data"><thead><tr>
     <th>Mercado</th><th>n</th><th>Base</th><th>BSS</th><th></th>
   </tr></thead><tbody>{bt}</tbody></table></div>
   <div class="warn"><b>Lo honesto:</b> el modelo muestra skill real en Over/Under
   2.5 (la línea principal), pero la muestra es chica (n={n2}) y ganarle al promedio
   histórico NO es ganarle a la línea de Polymarket, que ya lo incorpora. Es un buen
   modelo de research; para apostarlo de verdad hay que validarlo hacia adelante
   (registrar predicción vs línea live y medir el resultado real).</div>
 </section>

 <section>
   <div class="step">Resumen</div>
   <h2>Qué abre y qué no</h2>
   <p><b>Abre:</b> Over/Under total y por equipo, ambos anotan, marcador exacto,
   1X2 derivado de goles, hándicap. <b>No hace:</b> props de jugador, ni incorpora
   lesiones, alineaciones o clima. Es deliberadamente simple: estima goles a partir
   de la fuerza histórica de ataque y defensa, nada más.</p>
 </section>

 <footer>
   Modelo Poisson de goles, complementario al match-winner (Elo+Bayes+TrueSkill).
   Generado por el agente el {html.escape(generated_at)}. No es consejo financiero.
 </footer>
</div></body></html>"""
