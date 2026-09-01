# SKILL: Execution

## ROL EN EL PIPELINE
Convierte un SizingOutput en una orden real de Polymarket.
Valida el precio live, estima slippage, construye el payload del CLOB API,
y clasifica si la orden procede en AUTO o necesita REVIEW final.

## CUÁNDO INVOCAR
- Después de optimization/, cuando hay un SizingOutput válido
- El humano dice "ejecuta" o "procede con la apuesta"
- Un trade REVIEW fue aprobado por el humano (`scripts/orders.py --approve <key> --live`)

## CUÁNDO NO INVOCAR
- Sin pasar por risk/ y optimization/ primero (sin excepciones)
- Si el precio live ha movido más de X% vs el precio en la señal (re-evaluar desde research/)
- Si el mercado está a < min_hours_to_event del kickoff

## FUNCIONES DISPONIBLES

| Función | Qué hace | Input | Output |
|---|---|---|---|
| `price_validator.validate_live_price()` | Verifica que el precio live sea aceptable | signal_price, live_price, tolerance | bool |
| `slippage_estimator.estimate()` | Estima slippage dado el orderbook | token_id, size_usdc, orderbook | SlippageEstimate |
| `order_builder.build()` | Construye el payload para el CLOB API | RiskVerdict, SizingOutput, live_price | TradeOrder |
| `order_classifier.classify()` | Decide AUTO vs REVIEW para la ejecución final | TradeOrder, RiskVerdict | ExecutionDecision |
| `submit_order()` | Envía la orden REAL al CLOB V2 vía `venue/gateway` (LIMIT al tick; dry-run salvo gates live) | TradeOrder | OrderResult |
| `theta_exit.evaluate_exit()` | Regla PURA de salida del theta trade (TP desde min X / HARD min Y / STOP opcional) | entry, best_bid, minuto, ThetaExitConfig | (acción, razón) |

## SCHEMAS QUE CONSUME
- `optimization/schemas/sizing_output.SizingOutput`
- `risk/schemas/risk_verdict.RiskVerdict`

## SCHEMAS QUE PRODUCE
- `execution/schemas/trade_order.TradeOrder`
- `execution/schemas/execution_decision.ExecutionDecision`  ← output principal
- `execution/schemas/order_result.OrderResult`

## CONSTRAINTS
- NUNCA llamar submit_order() si ExecutionDecision.requires_approval == True
- NUNCA hardcodear credenciales de Polymarket — siempre de variables de entorno
- Si price_validator falla, NO re-intentar automáticamente — reportar al humano
- SIEMPRE guardar el OrderResult en el LocalState antes de retornar (via LocalStateClient);
  solo un fill `live` marca ejecutado — un dry_run NO (gotcha verificado, ver AGENTS.md)
- La idempotency_key DEBE verificarse contra el LocalState antes de submit_order()
- Apuestas fuera de estrategia: usar el carril **CIO override** —
  `scripts/propose_bet.py` (riesgo + REVIEW forzado + ledger) y colocar con
  `orders.py --approve`. Nunca llamar al broker directo.

## ERRORES COMUNES
- Llamar submit_order() en modo REVIEW (el error más costoso del sistema)
- No verificar idempotencia antes de enviar la orden (puede resultar en posición doble)
- Usar el precio de la señal en vez del precio live para construir la orden LIMIT
