# Registro de decisiones

## 2026-08-28 — Fuente de precio e indicadores

- Las señales se calculan sobre OHLC Heikin Ashi.
- Los precios Heikin Ashi son sintéticos y nunca se usan como precio ejecutado.
- Entrada, salida, MFE y MAE usan precios OHLC reales del mercado.
- MFE/MAE excluyen el recorrido de la vela de salida posterior a su apertura.

## 2026-08-28 — Momento de ejecución

- Una señal queda confirmada al cierre de su vela.
- La orden se ejecuta en el `open` real de la siguiente vela disponible.
- Una señal en la última vela del dataset no se ejecuta.

## 2026-08-28 — Datos reproducibles

- Binance REST permanece como adaptador externo.
- Los experimentos oficiales deben utilizar snapshots CSV con metadatos JSON.
- Los snapshots rechazan sobrescrituras accidentales.
- Solo se descargan velas ya cerradas.

## 2026-08-28 — Criterio inicial

- Se agrupan operaciones por mes UTC de salida.
- Cumple un mes cuando `wins / operaciones cerradas >= 70 %`.
- Los breakeven cuentan como operaciones no ganadoras.
- La evaluación también conserva P&L y número de muestras; un 70 % con pocas
  operaciones no se considerará evidencia suficiente en etapas posteriores.

## 2026-08-30 — Seguridad del adaptador Testnet

- La integración objetivo es Binance USD-M Futures Testnet, no Spot.
- Los defaults son `TRADING_ENABLED=false` y `DRY_RUN=true`.
- La configuración debe fallar ante valores inválidos.
- Los filtros del exchange se cachean y se procesan con `Decimal`.
- Las lecturas admiten tres reintentos con backoff 1, 2 segundos.
- Las mutaciones no se reintentan automáticamente.
- Ante timeout de creación se consulta el mismo `clientOrderId`; si no puede
  confirmarse, se eleva `BinanceUnknownOrderStateError`.
- Binance será la fuente de verdad; reconciliación y posiciones pertenecen a
  las siguientes fases.

## 2026-08-31 — Riesgo, persistencia y costes de Fase 2

- Los importes, precios y cantidades persistidos utilizan `Numeric/Decimal`.
- Los estados activos son `PENDING` y `OPEN`; toda discrepancia local/exchange
  bloquea nuevas entradas y requiere reconciliación explícita.
- El sizing arriesga un porcentaje de equity, se limita por nocional máximo y
  después se normaliza y valida contra filtros de Binance.
- Stops LONG redondean hacia abajo y stops SHORT hacia arriba.
- El backtest conserva precios de referencia y ejecución por separado.
- `pnl_pct` representa P&L neto para mantener compatibilidad con reportes.
- Comisión y slippage son configurables. El funding actual es una estimación
  fija por intervalo completo, no funding histórico observado.
- Sharpe se calcula sobre retornos por operación; no se presenta como Sharpe
  anualizado basado en retornos diarios.

## 2026-09-02 — Ejecución protegida y reconciliación de Fase 3

- `OrderExecutor` es la única frontera de aplicación autorizada para mutaciones.
- La cuenta debe operar en modo One-way; Hedge Mode se bloquea porque
  `reduceOnly` no es compatible con ese modo.
- Las órdenes condicionales usan el servicio Algo actual (`clientAlgoId` y
  `triggerPrice`), conservando consulta idempotente tras timeout.
- El stop inicial se recalcula con el precio promedio realmente ejecutado.
- Toda salida, stop y cierre de emergencia utiliza `reduceOnly=True`.
- Si falla la protección, se activa un kill switch unidireccional de runtime y
  se intenta cerrar inmediatamente la posición.
- El kill switch no modifica `.env`: domina la configuración hasta que el
  proceso sea auditado. Su persistencia entre reinicios queda para la fase del
  runner operativo.
- Una ausencia de posición solo se clasifica `STOP_LOSS` si historial y fills
  lo demuestran; de lo contrario se registra `EXTERNAL_CLOSE`.
- Las discrepancias no demostrables bloquean el sistema para revisión humana.

## 2026-09-02 — Runner y validación opt-in de Fase 4

- El MVP usa polling y procesa exclusivamente la última vela cerrada.
- Todo ciclo se persiste, incluso `NONE` y decisiones bloqueadas.
- Breakeven se evalúa en cada polling aunque la vela ya esté procesada.
- Una señal opuesta cierra la posición; no revierte en el mismo ciclo.
- No se implementa trailing hasta definir una regla explícita.
- El kill switch se persiste en `runtime_state` y sobrevive reinicios.
- Se permite una sola instancia local mediante file lock.
- Dry-run offline utiliza snapshots y equity simulada configurable.
- La integración Testnet es opt-in, exige cuenta neutral y solo limpia recursos
  cuyos identificadores pertenecen a la prueba.
- La limpieza es best effort: una caída externa puede requerir intervención.

## 2026-09-03 — Protocolo de investigación cuantitativa

- El snapshot `btcusdt_4h_2026_08` y las reglas actuales permanecen como
  baseline inmutable durante el diagnóstico.
- Winners y losers se clasifican por P&L neto; también se conserva el resultado
  bruto para separar señal y fricciones.
- Features candidatas usan solamente información disponible al cierre de la
  señal. MFE, MAE, trayectoria y duración se etiquetan como outcomes futuros.
- Los hallazgos de `QUANTITATIVE_RESEARCH_BASELINE.md` son hipótesis, no cambios
  aprobados de estrategia. Cualquier filtro requiere validación no solapada.

## 2026-09-03 — Resultado del experimento de contracción ATR

- Se probó únicamente `ATR(14) / media ATR(14, 20) <= 1.0`; no hubo barrido de
  parámetros y las salidas permanecieron sin cambios.
- Aunque mejoró expectancy y profit factor dentro de muestra, retuvo sólo 49 %
  de trades y 56.1 % del PnL positivo.
- La regla exacta se rechaza según los criterios pre-registrados y no se integra
  en la estrategia. Tampoco se considera validación fuera de muestra.

## 2026-09-05 — Dinámica ATR previa al reversal

- Se analizaron cambios ATR(14) de 1, 2 y 3 velas sin buscar thresholds ni
  modificar trades.
- La expansión incrementó la frecuencia de pérdidas <-3 %, pero no deterioró
  expectancy, PF, MAE y worst consistentemente en el conjunto.
- LONG sí mostró deterioro direccional en las tres ventanas; SHORT no. Se
  descarta cualquier regla ATR simétrica y no se integra filtro alguno.
- Una eventual regla LONG requiere pre-registro y datos no solapados. Escoger la
  mejor ventana retrospectivamente queda explícitamente prohibido.

## 2026-09-06 — Experimento DMI/ADX

- DMI/ADX(14) se calculó con Wilder RMA sobre OHLC real al cierre de la señal;
  SQZMOM permaneció sobre Heikin-Ashi.
- Los terciles ADX fueron exclusivamente descriptivos. No hubo búsqueda de
  thresholds ni cambios a la estrategia.
- ADX alto no produjo deterioro monotónico y counter+HIGH no concentró las
  pérdidas grandes; la hipótesis general se rechaza.
- La alineación DMI fue prometedora únicamente para SHORT y conservó dirección
  entre mitades y al retirar hasta dos peores trades. Sigue siendo una hipótesis
  in-sample, no una regla aprobada.

## 2026-09-06 — Encapsulación multi-estrategia

- La estrategia histórica pasa a llamarse `strategy_1`; sus reglas y parámetros
  quedan funcionalmente congelados.
- Heikin-Ashi e indicadores permanecen compartidos en `strategies/candles.py` y
  `strategies/indicators.py`; la interpretación de colores SQZMOM pertenece a
  `strategies/strategy_1/signals.py`.
- Backtest y runner consumen un contrato mínimo de estrategia y usan
  `strategy_1` como default. El engine continúa agnóstico.
- `strategies/signals.py` queda como fachada compatible temporal.
- No se implementa Strategy 2 ni infraestructura multi-timeframe anticipada.

## 2026-09-07 — Arquitectura experimental de Strategy 2

- La infraestructura multi-timeframe es compartida y causal; Strategy 2 no
  sincroniza datos por su cuenta y sólo recibe velas con `close_time < as_of`.
- La baseline determinista v1 es: EMA10/EMA55 diaria alineada, reversal SQZMOM
  4H y reversal SQZMOM 1H del mismo lado posterior al setup.
- Heikin-Ashi/SQZMOM se comparten; EMA, ATR, DMI/ADX y Disparity viven también
  en indicadores comunes y DMI/ADX de research consume esa única fórmula.
- OpenAI actúa como gate APPROVE/REJECT y como revisión HOLD/EXIT; nunca controla
  exchange, side, leverage, capital ni kill switch.
- Entradas fallan cerradas. En backtest, un cache miss requerido aborta
  explícitamente. Durante posición abierta, indisponibilidad AI se audita y no
  elimina protecciones deterministas ni inventa HOLD/EXIT.
- La configuración AI centraliza provider/model/reasoning/modo/cache/retries.
  Los prompts y schemas tienen versión, por lo que cambios invalidan cache.
- La asignación de capital Strategy 2 queda declarada en 1.0, distinta de
  leverage y nocional. No se inventó stop técnico ni definición de progreso.
- Strategy 2 permanece experimental, sin Testnet ni producción autorizados.
- El modelo inicial de research es `gpt-5.6-terra`; Sol y Luna permanecen como
  comparadores configurables. La selección no pertenece a Strategy 2.
- El contrato temporal y la causalidad viven íntegramente en `exchange/`.
  Se descartó un Protocol multi-timeframe sin consumidores dentro de
  `strategies/` para evitar confundir contrato estratégico con sincronización.

## 2026-09-09 — Preflight operativo para research AI

- `replay` nunca llama al proveedor; un miss aborta. `live` consulta primero la
  cache y sólo los misses pueden consumir presupuesto.
- La identidad de corrida fija bundle/hash, estrategia, modelo, reasoning,
  prompts, schemas y modo. Una reanudación incompatible se rechaza.
- La reconstrucción elegida es causal desde el bundle usando cache, con
  `last_processed_event` como checkpoint auditable; no se persiste una copia
  redundante de toda la máquina de estados.
- Cada intento live se registra `PENDING` antes de la llamada. Un timeout o corte
  deja estado `UNKNOWN` y bloquea reintentos automáticos para evitar duplicados.
- Los límites locales por coste y llamadas se reservan antes de cada intento;
  los cache hits no consumen esos límites.
- Los precios configurados corresponden a Terra al 2026-09-09 y deben verificarse
  contra documentación oficial antes de cada experimento live.

## 2026-09-10 — Collector ENTRY independiente

- Preflight, ENTRY collection y full backtest son modos mutuamente distinguibles.
- El collector reutiliza el recorrido causal flat del censo y el payload ENTRY
  del backtest. No importa ni llama ninguna operación de posición o EXIT.
- Una aprobación se registra como dato, pero no altera el estado de portfolio.
- Los misses de replay se registran como `MISSING` y no abortan el censo; el full
  backtest mantiene su semántica fail-closed original.
- `run_type=entry_collection` separa la identidad de corrida, mientras la cache
  de decisión permanece compartida para que el full backtest pueda reutilizarla.
- El dataset del collector contiene sólo información disponible al candidate;
  quedan prohibidos PnL, MFE/MAE y cualquier outcome futuro.

## 2026-09-11 — Auditoría pre-outcome de decisiones ENTRY

- El run Terra produjo 8 APPROVE, todos SHORT, y 73 REJECT. Esta distribución
  queda registrada como comportamiento del reviewer, no como evidencia de edge.
- Los APPROVE comparten alineación DMI bajista 1D/4H/1H; los LONG rechazados
  muestran conflictos 4H/1H y una posible ambigüedad porque el AI sólo recibió
  el valor SQZMOM, no su color/cambio de reversal.
- Confidence no separa decisiones y los reason codes libres están fragmentados.
- No se modifica prompt, schema ni Strategy 2 hasta abrir outcomes en una tarea
  posterior explícita. Todas las conclusiones actuales son pre-outcome.

## 2026-09-13 — Contrato experimental ENTRY V2

- Se conserva V1 byte-semánticamente reproducible y como default.
- V2 sólo hace explícitas dirección y dinámica/color SQZMOM de las velas que ya
  generan setup 4H y confirmación 1H; no añade señales, indicadores ni outcomes.
- V2 usa prompt `strategy2-entry-v2`, schema `1.1.0` y reason codes cerrados, por
  lo que su identidad de cache no puede reutilizar decisiones V1.
- El live V2 queda pendiente de autorización y de resolver la reserva máxima
  `$2.514` frente al límite local `$2.50`; no se incrementa automáticamente.
