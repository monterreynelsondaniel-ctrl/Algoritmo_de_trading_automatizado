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
