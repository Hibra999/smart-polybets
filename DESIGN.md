---
name: PEPA
description: Mesa cuantitativa nocturna para predicciones y backtests deportivos
colors:
  operator-blue: "#2563EB"
  signal-cyan: "#22D3EE"
  night: "#0F1117"
  analysis-surface: "#1A1D27"
  raised-surface: "#22262F"
  boundary: "#2D3340"
  primary-text: "#E2E8F0"
  secondary-text: "#94A3B8"
  success: "#10B981"
  warning: "#F59E0B"
  danger: "#EF4444"
typography:
  headline:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "2.25rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.35
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.04em"
  numeric:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "0.875rem"
    fontWeight: 700
    lineHeight: 1.4
rounded:
  compact: "4px"
  control: "8px"
  surface: "12px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  report-card:
    backgroundColor: "{colors.analysis-surface}"
    textColor: "{colors.primary-text}"
    rounded: "{rounded.surface}"
    padding: "20px"
  model-chip:
    backgroundColor: "{colors.raised-surface}"
    textColor: "{colors.secondary-text}"
    rounded: "{rounded.control}"
    padding: "3px 10px"
  status-success:
    backgroundColor: "{colors.analysis-surface}"
    textColor: "{colors.success}"
    rounded: "{rounded.control}"
    padding: "4px 12px"
---

# Design System: PEPA

## 1. Overview

**Creative North Star: "La Mesa Nocturna"**

PEPA se siente como una mesa cuantitativa abierta durante la noche: silenciosa,
concentrada y densa en evidencia. La interfaz desaparece detrás del trabajo; el ritmo lo
marcan el fixture, el modelo, el mercado y el corte temporal.

La creatividad sólo aparece cuando explica una relación: consenso entre modelos,
trayectoria del bankroll o distancia contra un target. Nunca debe parecer un casino, una
casa de apuestas promocional ni un dashboard de neón.

**Key Characteristics:**

- Fondo nocturno con capas tonales, sin sombras decorativas.
- Tipografía Inter para lectura y JetBrains Mono para todo valor cuantitativo.
- Densidad controlada, jerarquía directa y estado siempre expresado con texto.
- Una misma estructura responsive para predicción y backtest.

## 2. Colors

Una base azul-negra estable deja que Operator Blue y Signal Cyan aparezcan sólo cuando
una relación merece atención.

### Primary

- **Operator Blue:** acción o selección principal; nunca como relleno ornamental.
- **Signal Cyan:** edge, dato destacado y línea de referencia analítica.

### Secondary

- **Success:** target cumplido o resultado favorable, siempre acompañado por texto.
- **Warning:** revisión o dato incompleto.
- **Danger:** target fallido, pérdida o bloqueo.

### Neutral

- **Night:** lienzo de todo reporte.
- **Analysis Surface:** superficie primaria para bloques de decisión.
- **Raised Surface:** chips, filas alternas y controles compactos.
- **Boundary:** separadores y bordes estructurales.
- **Primary Text / Secondary Text:** contenido y metadatos, respectivamente.

**The Rare Signal Rule.** Cyan y azul juntos ocupan menos del 15% de la superficie; su
rareza mantiene su significado.

## 3. Typography

**Display Font:** Inter (system-ui como fallback)
**Body Font:** Inter (system-ui como fallback)
**Label/Mono Font:** JetBrains Mono (ui-monospace como fallback)

**Character:** una sola sans mantiene familiaridad de producto; el mono separa datos de
narrativa sin convertir todo el reporte en una terminal.

### Hierarchy

- **Headline** (700, 2.25rem, 1.2): título único del reporte.
- **Title** (600, 1.125rem, 1.35): partido o bloque analítico.
- **Body** (400, 1rem, 1.6): explicaciones con un máximo de 72 caracteres por línea.
- **Label** (600, 0.75rem, 0.04em): nombres breves de métrica.
- **Numeric** (700, 0.875rem, 1.4): probabilidades, dinero, fechas y conteos.

**The Numeric Truth Rule.** Todo número decisivo usa mono; ningún adjetivo sustituye el
valor, la muestra o el corte temporal.

## 4. Elevation

El sistema es plano por defecto. La profundidad nace de tres tonos de superficie y del
borde Boundary; no hay sombras ambientales en reposo.

**The No Casino Glow Rule.** Ningún componente usa resplandor, blur o neón para simular
importancia.

## 5. Components

### Chips

- **Style:** fondo Raised Surface, texto secundario y valor mono en texto primario.
- **State:** el color semántico complementa una etiqueta textual; nunca la reemplaza.

### Cards / Containers

- **Corner Style:** curva contenida de 12px.
- **Background:** Analysis Surface sobre Night.
- **Shadow Strategy:** ninguna; profundidad tonal y borde de 1px.
- **Border:** Boundary, siempre estructural.
- **Internal Padding:** 20px; 16px en móvil.

### Prediction Strip

Cada modelo ocupa una fila con nombre, probabilidad y barra proporcional. El consenso se
entiende aun sin color y los desacuerdos quedan expuestos, no promediados en silencio.

### Performance Table

Encabezados persistentes en significado, valores alineados por decimal y filas recientes
limitadas a lo necesario para auditar el resumen.

## 6. Do's and Don'ts

### Do:

- **Do** mostrar torneo, temporada, fecha de corte, fuente y tamaño de muestra.
- **Do** usar Night, Analysis Surface y Boundary como gramática compartida.
- **Do** acompañar verde, ámbar y rojo con palabras como Cumple, Revisar o Falla.
- **Do** respetar WCAG AA y una estructura legible sin fuentes remotas.

### Don't:

- **Don't** hacer que parezca un casino, una casa de apuestas promocional ni un dashboard de neón.
- **Don't** usar gradientes decorativos, glassmorphism o animación gratuita.
- **Don't** mostrar métricas sin contexto, fuente, muestra o fecha de corte.
- **Don't** depender sólo del color para comunicar éxito, riesgo o pérdida.
- **Don't** usar franjas laterales de color, sombras amplias o tarjetas anidadas.
