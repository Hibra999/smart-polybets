"""Presentación HTML (tipo deck) que explica la arquitectura del sistema para una
audiencia general: qué es, cómo funciona, los módulos, ventajas y desventajas, y
por qué es una buena opción para el trading deportivo agéntico.

Design system pypro.mx ("Editor at Night"): dark (#0F1117), Operator Blue
(#2563EB), acento cyan (#22D3EE), Inter + JetBrains Mono. Sin emojis-bullet, sin
em-dashes en el copy, sin gradientes ruidosos.

Función pura: `build_architecture_deck(generated_at)` devuelve el HTML completo.
El contenido está fundado en el mapa de módulos real del repo (ver CLAUDE.md).
"""
from __future__ import annotations

import html

# ── Contenido (fundado en el repo) ───────────────────────────────────────────

# Las seis etapas del pipeline, en orden de ejecución de los workflows.
PIPELINE = [
    ("Research", "research/", "Mira el mercado y busca diferencias",
     "Lee los datos del torneo, corre los modelos (Elo, Bayes, TrueSkill) y los "
     "contrasta con el precio de Polymarket. Si el modelo cree que un equipo gana "
     "mas seguido de lo que el precio implica, marca esa diferencia como una "
     "oportunidad con su edge."),
    ("Risk", "risk/", "Decide si vale la pena y cuanto arriesgar",
     "Es el guardian. Toma cada oportunidad y aplica las reglas escritas en el "
     "STRATEGY.md del torneo: tamano de muestra, confianza del modelo, umbral de "
     "edge. Emite un veredicto AUTO (operar solo), REVIEW (pide tu visto bueno) o "
     "DISCARD (descartar)."),
    ("Optimization", "optimization/", "Afina el tamano de la apuesta",
     "Refina el sizing con Kelly fraccional (o un optimizador convexo si esta "
     "disponible). Kelly responde a una sola pregunta: dado el edge y la cuota, "
     "cuanto del bankroll apostar para crecer sin arruinarse."),
    ("Execution", "execution/", "Arma y manda la orden",
     "Construye la orden con el token, el precio y el tamano exactos, y la envia a "
     "Polymarket. Por defecto opera en dry-run (simulado) con un kill-switch; solo "
     "con autorizacion explicita y en modo live manda dinero real."),
    ("Portfolio", "portfolio/", "Lleva la cuenta del estado real",
     "Es el puente con la fuente unica de verdad (la app de estado). Registra "
     "posiciones, evita duplicar una misma apuesta con una clave de idempotencia y "
     "calcula el PnL. El repo no guarda estado propio: pregunta."),
    ("Editorial", "editorial/", "Explica lo que se hizo y por que",
     "Convierte cada decision en lenguaje claro: reportes HTML, resumenes y hasta "
     "tweets. Esta misma presentacion sale de aqui. La transparencia es parte del "
     "producto, no un extra."),
]

# Modulos de soporte (no son etapas del flujo, son los cimientos).
FOUNDATION = [
    ("core/", "Tipos, excepciones y utilidades compartidas. Cero logica de "
     "negocio: el vocabulario comun que todos hablan."),
    ("data/", "Un SQLite por torneo con un esquema canonico por deporte. Datos "
     "historicos, partidos y cuotas, versionados y reproducibles."),
    ("adapters/", "La unica capa que lee los datos (de solo lectura) y la que "
     "aloja los modelos de rating (Elo, Bayes, TrueSkill)."),
    ("tournaments/", "La configuracion de cada torneo y, sobre todo, el "
     "STRATEGY.md: la unica fuente de reglas. Ningun umbral vive en el codigo."),
    ("agent/", "El cerebro operativo: las instrucciones de Claude, las "
     "herramientas, los workflows y los prompts que orquestan todo."),
    ("tests/", "Casi cien pruebas que fijan los contratos. Si algo cambia un "
     "comportamiento aprobado, una prueba se pone en rojo."),
]

# Los tres modelos, explicados en una linea para audiencia general.
MODELS = [
    ("Elo", "El mismo sistema del ajedrez. Cada equipo tiene un numero; le sube "
     "al que gana y le baja al que pierde, mas fuerte si el rival era mejor."),
    ("Bayes", "Parte de una creencia inicial y la actualiza con cada resultado. "
     "Cuantos menos partidos vio, mas humilde es su prediccion."),
    ("TrueSkill", "El sistema de emparejamiento de los videojuegos. No solo "
     "estima la habilidad, tambien que tan seguro esta de esa estimacion."),
]

ADVANTAGES = [
    ("Reproducible hacia adelante", "Los mismos datos producen siempre la misma "
     "decision. Nada de corazonadas: cada apuesta se puede auditar y repetir."),
    ("Las reglas viven fuera del codigo", "Los umbrales estan en archivos de "
     "estrategia legibles. Cambiar la politica de riesgo no requiere tocar Python "
     "ni arriesgar un bug."),
    ("El humano manda en lo ambiguo", "Lo obvio se delega (AUTO); lo dudoso "
     "escala a tu aprobacion (REVIEW). Vos sos el director de inversiones, no el "
     "que llena formularios."),
    ("Tres modelos, no uno", "Elo, Bayes y TrueSkill votan juntos. Cuando "
     "discrepan, el sistema baja la confianza en vez de fingir certeza."),
    ("Seguro por defecto", "Arranca simulado, con kill-switch. El dinero real "
     "solo sale con una autorizacion explicita y deja rastro on-chain."),
    ("Honesto sobre su edge", "El backtest mostro que el modelo de ratings no "
     "tiene ventaja robusta en NFL. El sistema lo dice en vez de venderte humo."),
]

DISADVANTAGES = [
    ("Los modelos de rating no son magia", "Predicen el ganador a partir de la "
     "fuerza historica, no de lesiones, alineaciones ni clima. El edge real suele "
     "estar en datos que estos modelos no ven."),
    ("Una buena temporada no es una ventaja", "El backtest dejo claro que un ano "
     "ganador puede ser pura varianza. Validar fuera de muestra es obligatorio, no "
     "opcional."),
    ("Depende de cuotas y liquidez", "Si Polymarket no tiene mercado o esta seco, "
     "no hay operacion. El sistema vale lo que valen sus datos de entrada."),
    ("No es asesoria financiera", "Es una herramienta cuantitativa para un "
     "operador que entiende el riesgo. Podes perder el capital que pongas."),
    ("Requiere mantenimiento", "Esquemas, datos y estrategias hay que "
     "actualizarlos. Es un instrumento de precision, no un boton magico."),
]

WHY_GOOD = [
    ("La disciplina es el verdadero alfa", "La mayoria pierde por apostar de mas, "
     "perseguir perdidas o cambiar de criterio. Un agente con reglas fijas y Kelly "
     "no se cansa, no se emociona y no improvisa."),
    ("Velocidad con criterio humano", "Procesa todos los partidos del dia en "
     "segundos y te entrega solo lo que merece una decision, ya dimensionado y "
     "justificado. Vos aprobas, no calculas."),
    ("Cada decision deja papel", "Idempotencia, sellos de tiempo y reportes hacen "
     "que toda apuesta sea trazable. Cuando algo sale mal, sabes exactamente por "
     "que se hizo."),
    ("Crece de deporte en deporte", "El mismo esqueleto ya corre Mundial y NFL. "
     "Agregar un deporte es agregar datos y una estrategia, no reescribir el "
     "motor."),
]


def _stage_card(i: int, name: str, path: str, tag: str, body: str) -> str:
    return f"""
      <article class="stage">
        <div class="stage-n num">{i:02d}</div>
        <div class="stage-body">
          <div class="stage-h">
            <h3>{html.escape(name)}</h3>
            <code>{html.escape(path)}</code>
          </div>
          <p class="tag">{html.escape(tag)}</p>
          <p>{html.escape(body)}</p>
        </div>
      </article>"""


def _li(title: str, body: str, mark: str) -> str:
    return f"""
      <li class="point point-{mark}">
        <b>{html.escape(title)}</b>
        <span>{html.escape(body)}</span>
      </li>"""


def _chip(name: str, body: str) -> str:
    return f"""
      <div class="model">
        <h4>{html.escape(name)}</h4>
        <p>{html.escape(body)}</p>
      </div>"""


def _foundation(path: str, body: str) -> str:
    return f"""
      <div class="found">
        <code>{html.escape(path)}</code>
        <p>{html.escape(body)}</p>
      </div>"""


def build_architecture_deck(generated_at: str = "") -> str:
    """Devuelve el HTML completo de la presentacion (un solo archivo, sin deps)."""
    stages = "".join(_stage_card(i + 1, *s) for i, s in enumerate(PIPELINE))
    foundation = "".join(_foundation(p, b) for p, b in FOUNDATION)
    models = "".join(_chip(n, b) for n, b in MODELS)
    adv = "".join(_li(t, b, "up") for t, b in ADVANTAGES)
    dis = "".join(_li(t, b, "down") for t, b in DISADVANTAGES)
    why = "".join(_li(t, b, "star") for t, b in WHY_GOOD)
    gen = html.escape(generated_at)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Como funciono, Sports Quant Trading</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#0F1117; --surface:#1A1D27; --surface-alt:#22262F; --border:#2D3340;
    --text:#E2E8F0; --muted:#94A3B8; --blue:#2563EB; --cyan:#22D3EE;
    --green:#10B981; --amber:#F59E0B; --red:#EF4444;
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{ margin:0; background:var(--bg); color:var(--text);
    font-family:Inter,system-ui,sans-serif; line-height:1.65;
    -webkit-font-smoothing:antialiased; }}
  .num {{ font-family:'JetBrains Mono',ui-monospace,monospace; }}
  .muted {{ color:var(--muted); }}
  code {{ font-family:'JetBrains Mono',ui-monospace,monospace; font-size:.8rem;
    color:var(--cyan); background:#22D3EE10; border:1px solid #22D3EE22;
    border-radius:6px; padding:1px 7px; }}

  section {{ min-height:100vh; display:flex; flex-direction:column; justify-content:center;
    padding:80px 24px; border-bottom:1px solid var(--border); scroll-margin-top:0; }}
  .inner {{ max-width:960px; margin:0 auto; width:100%; }}
  .eyebrow {{ font-size:.75rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase;
    color:var(--cyan); margin-bottom:14px; }}
  h1 {{ font-size:clamp(2.4rem,6vw,4rem); font-weight:900; letter-spacing:-.03em;
    line-height:1.04; margin:0 0 20px; }}
  h2 {{ font-size:clamp(1.8rem,4vw,2.6rem); font-weight:800; letter-spacing:-.02em;
    margin:0 0 12px; }}
  .lead {{ font-size:clamp(1.05rem,2vw,1.3rem); color:var(--muted); max-width:680px; }}
  .sub {{ color:var(--muted); max-width:680px; margin:0 0 36px; }}

  /* cover */
  .cover h1 span {{ color:var(--blue); }}
  .cover .tagline {{ display:inline-block; margin-top:8px; font-size:.95rem;
    color:var(--muted); border:1px solid var(--border); border-radius:9999px;
    padding:8px 18px; }}
  .scroll-hint {{ margin-top:48px; color:var(--muted); font-size:.8rem; letter-spacing:.1em;
    text-transform:uppercase; }}

  /* pipeline stages */
  .stages {{ display:flex; flex-direction:column; gap:14px; margin-top:8px; }}
  .stage {{ display:flex; gap:20px; background:var(--surface); border:1px solid var(--border);
    border-radius:14px; padding:22px 24px; transition:border-color .2s; }}
  .stage:hover {{ border-color:var(--blue); }}
  .stage-n {{ font-size:1.5rem; font-weight:700; color:var(--blue); min-width:42px; }}
  .stage-h {{ display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }}
  .stage-h h3 {{ margin:0; font-size:1.25rem; font-weight:700; }}
  .stage .tag {{ color:var(--cyan); font-weight:600; margin:6px 0 4px; font-size:.95rem; }}
  .stage p:last-child {{ margin:0; color:var(--muted); }}

  /* flow chips */
  .flow {{ display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin:28px 0 8px; }}
  .flow .f {{ background:var(--surface-alt); border:1px solid var(--border); border-radius:9999px;
    padding:8px 16px; font-weight:600; font-size:.9rem; }}
  .flow .arrow {{ color:var(--blue); font-weight:700; }}

  /* foundation grid */
  .founds {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
    gap:14px; margin-top:8px; }}
  .found {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:18px 20px; }}
  .found code {{ font-size:.85rem; }}
  .found p {{ margin:10px 0 0; color:var(--muted); font-size:.95rem; }}

  /* models */
  .models {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:16px; margin-top:8px; }}
  .model {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:22px; }}
  .model h4 {{ margin:0 0 8px; font-size:1.2rem; color:var(--cyan); }}
  .model p {{ margin:0; color:var(--muted); font-size:.95rem; }}

  /* point lists */
  ul.points {{ list-style:none; padding:0; margin:8px 0 0; display:grid;
    grid-template-columns:repeat(auto-fill,minmax(380px,1fr)); gap:14px; }}
  .point {{ background:var(--surface); border:1px solid var(--border); border-radius:12px;
    padding:18px 20px 18px 48px; position:relative; }}
  .point b {{ display:block; font-size:1.02rem; margin-bottom:4px; }}
  .point span {{ color:var(--muted); font-size:.95rem; }}
  .point::before {{ position:absolute; left:18px; top:18px; font-weight:700;
    font-family:'JetBrains Mono',monospace; }}
  .point-up::before {{ content:"+"; color:var(--green); }}
  .point-down::before {{ content:"-"; color:var(--amber); }}
  .point-star::before {{ content:">"; color:var(--blue); }}

  /* example walk */
  .walk {{ background:var(--surface); border:1px solid var(--border); border-radius:14px;
    padding:8px 26px; margin-top:8px; }}
  .walk .row {{ display:flex; gap:18px; padding:18px 0; border-bottom:1px solid var(--border); }}
  .walk .row:last-child {{ border-bottom:0; }}
  .walk .step {{ color:var(--blue); font-weight:700; min-width:120px; }}
  .walk .what {{ color:var(--muted); }}
  .walk .what b {{ color:var(--text); }}

  footer {{ padding:56px 24px; text-align:center; color:var(--muted); font-size:.85rem; }}
  footer .inner {{ border-top:1px solid var(--border); padding-top:28px; }}
  @media (max-width:560px) {{
    section {{ padding:64px 18px; }}
    .stage {{ flex-direction:column; gap:8px; }}
    ul.points {{ grid-template-columns:1fr; }}
    .walk .row {{ flex-direction:column; gap:4px; }}
  }}
</style>
</head>
<body>

  <section class="cover">
    <div class="inner">
      <div class="eyebrow">Sports Quant Trading System</div>
      <h1>Un fondo de cobertura<br>de <span>una sola persona</span>,<br>operado por un agente.</h1>
      <p class="lead">Soy un sistema que analiza mercados de prediccion deportiva en
      Polymarket, dimensiona el riesgo y opera, mientras vos decidis lo ambiguo.
      Esta es la explicacion de como funciono.</p>
      <div><span class="tagline num">Research &rarr; Risk &rarr; Optimization &rarr; Execution &rarr; Portfolio &rarr; Editorial</span></div>
      <div class="scroll-hint">Desliza para recorrer la arquitectura</div>
    </div>
  </section>

  <section>
    <div class="inner">
      <div class="eyebrow">Que soy</div>
      <h2>Un analista, un gestor de riesgo y un operador, en un mismo sistema</h2>
      <p class="sub">Imagina un fondo donde una sola persona es el director de
      inversiones y todo lo demas lo hace una maquina disciplinada. Yo soy esa
      maquina. Estudio quien es mas probable que gane, comparo esa estimacion con
      el precio que paga el mercado y, cuando hay una diferencia a favor, propongo
      una apuesta del tamano justo. Lo obvio lo ejecuto solo; lo dudoso te lo paso
      a vos.</p>
      <div class="flow">
        <span class="f">Datos</span><span class="arrow">&rarr;</span>
        <span class="f">Modelos</span><span class="arrow">&rarr;</span>
        <span class="f">Edge</span><span class="arrow">&rarr;</span>
        <span class="f">Riesgo</span><span class="arrow">&rarr;</span>
        <span class="f">Tamano</span><span class="arrow">&rarr;</span>
        <span class="f">Orden</span>
      </div>
    </div>
  </section>

  <section>
    <div class="inner">
      <div class="eyebrow">Principio rector</div>
      <h2>Reproducibilidad hacia adelante</h2>
      <p class="lead">Cada decision es el resultado determinista de datos
      documentados, procesados por funciones versionadas con contratos explicitos.
      Los mismos datos de entrada producen siempre la misma decision. No hay
      corazonadas ni cajas negras: todo se puede auditar y repetir. Esa es la
      diferencia entre un sistema y una apuesta de bar.</p>
    </div>
  </section>

  <section>
    <div class="inner">
      <div class="eyebrow">Como funciono, paso a paso</div>
      <h2>Seis etapas, una sola direccion</h2>
      <p class="sub">Cada oportunidad recorre el mismo camino. Cada etapa hace una
      cosa y se la pasa a la siguiente con un contrato claro.</p>
      <div class="stages">{stages}</div>
    </div>
  </section>

  <section>
    <div class="inner">
      <div class="eyebrow">Un ejemplo real</div>
      <h2>Que pasa con un partido del Mundial</h2>
      <div class="walk">
        <div class="row"><div class="step num">Research</div><div class="what">Los modelos dan a <b>Uruguay 80.7%</b> de ganar. Polymarket lo paga como <b>66.5%</b>. Hay una diferencia de <b>+14.2%</b> a favor.</div></div>
        <div class="row"><div class="step num">Risk</div><div class="what">El guardian ve que Elo esta alto pero Bayes y TrueSkill discrepan. Baja la confianza a <b>LOW</b> y marca <b>REVIEW</b>: no opera solo, te pregunta.</div></div>
        <div class="row"><div class="step num">Optimization</div><div class="what">Con el edge y la cuota, Kelly calcula el tamano y lo limita al tope de seguridad.</div></div>
        <div class="row"><div class="step num">Execution</div><div class="what">Con tu visto bueno, arma la orden con el token y precio exactos y la manda. Queda <b>matched</b> on-chain.</div></div>
        <div class="row"><div class="step num">Portfolio</div><div class="what">Registra la posicion con su clave de idempotencia para no volver a apostar lo mismo, y sigue el PnL.</div></div>
        <div class="row"><div class="step num">Editorial</div><div class="what">Escribe el reporte del dia explicando el pick, el edge y por que fue REVIEW.</div></div>
      </div>
    </div>
  </section>

  <section>
    <div class="inner">
      <div class="eyebrow">Los cimientos</div>
      <h2>Lo que sostiene al pipeline</h2>
      <p class="sub">Debajo de las seis etapas hay una base que casi nunca cambia:
      datos, tipos, reglas y pruebas.</p>
      <div class="founds">{foundation}</div>
    </div>
  </section>

  <section>
    <div class="inner">
      <div class="eyebrow">Como estimo quien gana</div>
      <h2>Tres modelos que votan juntos</h2>
      <p class="sub">No confio en un solo metodo. Combino tres formas distintas de
      medir fuerza, y cuando no se ponen de acuerdo, lo tomo como senal de que hay
      que ser prudente.</p>
      <div class="models">{models}</div>
    </div>
  </section>

  <section>
    <div class="inner">
      <div class="eyebrow">Ventajas</div>
      <h2>Por que esta forma de operar es solida</h2>
      <ul class="points">{adv}</ul>
    </div>
  </section>

  <section>
    <div class="inner">
      <div class="eyebrow">Desventajas y limites</div>
      <h2>Lo que NO hago, dicho sin maquillaje</h2>
      <p class="sub">Un sistema honesto declara sus limites. Estos son los mios.</p>
      <ul class="points">{dis}</ul>
    </div>
  </section>

  <section>
    <div class="inner">
      <div class="eyebrow">La tesis</div>
      <h2>Por que es una buena opcion para el trading deportivo agentico</h2>
      <p class="sub">El edge no siempre esta en el modelo. Muchas veces esta en la
      disciplina, la velocidad y la trazabilidad. Ahi es donde un agente gana.</p>
      <ul class="points">{why}</ul>
    </div>
  </section>

  <footer>
    <div class="inner">
      Sports Quant Trading System, presentacion generada por el agente{f' el {gen}' if gen else ''}.<br>
      Herramienta cuantitativa para un operador que entiende el riesgo. No es consejo financiero.
    </div>
  </footer>

</body>
</html>"""
