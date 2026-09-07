# Strategy 2 — arquitectura multi-timeframe y decisiones OpenAI

Fecha: 2026-09-07. Estado: **experimental / sin backtest cuantitativo**.

## A. Auditoría inicial

La rama inicial fue `main`, HEAD `2ebca81`, siete commits por delante de
`origin/main` y working tree limpio. La suite PRE ejecutó 51 tests correctamente
(una integración Binance opt-in omitida).

La baseline PRE de Strategy 1 fue 176 señales, 100 trades cerrados y uno abierto:

| Métrica | PRE |
|---|---:|
| Win rate | 51.00 % |
| P&L neto | -25.0992807215 % |
| Compuesto | -30.0154016164 % |
| Profit factor | 0.8303556087 |
| LONG | -24.1839326543 % |
| SHORT | -0.9153480672 % |

## B. Arquitectura seleccionada

```text
snapshots REST/bundle ──> MultiTimeframeMarketData (cierre causal)
                              │
shared candles + indicators ──┤
                              v
Strategy 2: 1D trend -> 4H setup -> 1H confirmation
                              │ candidate
                              v
AI entry gate -> raw next-open execution -> 4H AI exit reviews
                    cache/audit <──┘
```

La sincronización vive en `exchange/multi_timeframe.py`, no dentro de Strategy
2. Un `view_at(T)` sólo expone filas con `close_time < T`; esto expresa cuándo
la vela era realmente conocida y evita unir retrospectivamente una vela diaria
o 4H todavía abierta.

Los bundles son manifests que referencian snapshots inmutables por timeframe y
validan símbolo/timeframe. No se modificó el snapshot oficial de Strategy 1.

## C. Flujo exacto de Strategy 2 v1

1. Tendencia diaria: LONG si EMA10 > EMA55; SHORT si EMA10 < EMA55.
2. Setup: reversal SQZMOM 4H alineado con esa dirección.
3. Confirmación: reversal SQZMOM 1H del mismo lado y con cierre posterior al
   cierre del setup.
4. Se construye un candidate determinista e identificador reproducible.
5. ENTRY REVIEW debe devolver APPROVE/REJECT bajo schema estricto. Error,
   refusal, inconsistencia de side o cache miss implica no entrada; en backtest
   requerido aborta explícitamente.
6. La ejecución simulada usa el open OHLC real siguiente con fricciones, nunca
   precio Heikin-Ashi.
7. Con posición abierta, cada cierre 4H nuevo genera EXIT REVIEW HOLD/EXIT y
   registra PnL no realizado, MFE, MAE y `bars_since_entry`.

No se definieron setup expiration, time stop, progreso significativo, stop
técnico, extremos de rango ni thresholds ADX/SQZMOM. Los contratos permiten
añadirlos después de investigación, sin disfrazarlos hoy como reglas validadas.

## D. Indicadores compartidos

- Heikin-Ashi y SQZMOM existentes permanecen sin cambio.
- Se añadieron EMA, Wilder RMA, DMI/ADX y Disparity configurables.
- DMI/ADX usa OHLC real; SQZMOM usa HA.
- El experimento ADX ahora consume la fórmula común, eliminando duplicación.
- Volume Profile queda fuera: todavía no existe una definición aceptada.

## E. Integración OpenAI

El adaptador usa el SDK Python oficial y `client.responses.create`, con
`text.format` JSON Schema estricto. El SDK desactiva sus retries internos y la
capa propia realiza como máximo dos intentos configurables, sólo para timeout,
conexión, 429 temporal o 5xx; errores de quota/billing y schema no se repiten.
Respeta `retry_after` cuando el error lo expone.

Provider, modelo, reasoning effort, modo, timeout/cache y retries están
centralizados. El default de research es `gpt-5.6-terra`: la documentación
oficial confirma que Terra, `gpt-5.6-sol` y `gpt-5.6-luna` soportan Responses y
Structured Outputs. Los mismos candidates pueden compararse cambiando
`OPENAI_MODEL`; modelo distinto produce intencionalmente otra clave de cache.
El proyecto fija `openai==3.8.0`, versión oficial actual verificada al momento
de esta revisión.

Cada clave contiene tipo de decisión, input canónico, modelo, reasoning, prompt
y schema. SQLite conserva payload/output y metadata (response id, uso y
latencia cuando existen), más un audit append-only de live/cache/error. Nunca
se guardan llaves ni headers.

Referencias oficiales: [OpenAI Python SDK](https://github.com/openai/openai-python),
[Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs).

## F. Backtest y reproducibilidad

```bash
.venv/bin/python -m backtest.strategy_2_run --bundle NOMBRE_BUNDLE
```

El default es replay y no llama a OpenAI. `--ai-live` es opt-in, requiere
`OPENAI_API_KEY` y puede generar costo. El output registra bundle, versión de
estrategia, modo, modelo, prompts, schema, decisiones, errores y trades.

No se ejecutó backtest Strategy 2 porque el repositorio aún no contiene un
snapshot/bundle 1D+4H+1H ni decisiones cacheadas. Inventar o descargar datos
habría violado el alcance. Por ello no se reportan P&L, approval rate ni una
comparación inexistente.

## G. Seguridad y política de fallos

- La IA no puede enviar órdenes ni cambiar side, leverage, allocation o riesgo.
- Un side AI opuesto invalida la respuesta.
- Las entradas nunca se aprueban por fallback.
- Durante una posición, fallo AI se registra como estado desconocido; no se
  interpreta como HOLD ni EXIT y las protecciones deterministas continúan.
- Strategy 2 no está conectada al runner Testnet ni habilitada para producción.
- `TRADING_ENABLED`, `DRY_RUN` y kill switch permanecen intactos.

## H. Estado de Strategy 2

Implementado: infraestructura causal, indicadores comunes, configuración y
estado, candidate determinista, schemas/prompts, adaptador OpenAI, validación,
retries acotados, cache/auditoría y motor de backtest AI-aware.

Pendiente: bundle real MTF, lote cacheado, stop técnico, ubicación/estructura
formal, Volume Profile, reglas objetivas de progreso/salida, integración con
OrderExecutor/Testnet y validación cuantitativa/fuera de muestra.

## I. Compatibilidad Strategy 1

Strategy 1 conserva sus módulos, snapshot, señales y engine. La única migración
compartida sobre research fue DMI/ADX; no participa en su señal ni backtest. La
validación final confirmó:

| Métrica | PRE | POST |
|---|---:|---:|
| Señales | 176 | 176 |
| Trades cerrados | 100 | 100 |
| Trade abierto final | 1 | 1 |
| Win rate | 51.00 % | 51.00 % |
| P&L neto | -25.0992807215 % | -25.0992807215 % |
| Compuesto | -30.0154016164 % | -30.0154016164 % |
| Profit factor | 0.8303556087 | 0.8303556087 |
| LONG | -24.1839326543 % | -24.1839326543 % |
| SHORT | -0.9153480672 % | -0.9153480672 % |

La suite POST ejecutó 64 tests correctamente y omitió únicamente la integración
Binance opt-in. También pasaron compilación de imports, `git diff --check` y la
verificación de que ambos archivos del snapshot Strategy 1 no cambiaron.

## J. Riesgos y deuda

- La calidad de Strategy 2 es desconocida hasta obtener datos y decisiones.
- Las decisiones de un modelo no son deterministas en sentido matemático; la
  cache/versionado es obligatoria para reproducibilidad experimental.
- El schema compacto facilita análisis, pero reason codes siguen siendo output
  de modelo y requieren evaluación empírica.
- La persistencia AI usa SQLite independiente; una migración unificada puede
  evaluarse antes de producción, sin acoplar research a `trades`.
