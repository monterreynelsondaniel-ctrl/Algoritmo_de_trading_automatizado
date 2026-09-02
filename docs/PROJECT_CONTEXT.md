# Contexto del proyecto

## Objetivo actual

Validar una estrategia sencilla de reversión SQZMOM sobre futuros BTCUSDT en
temporalidad de cuatro horas. El criterio preliminar es alcanzar al menos 70 %
de operaciones ganadoras en cada mes evaluado.

## Flujo de datos

1. `exchange/market_data.py` obtiene velas cerradas desde Binance REST.
2. `data/frozen_market_data.py` guarda y recupera snapshots reproducibles.
3. `strategies/candles.py` deriva OHLC Heikin Ashi conservando OHLC real.
4. `strategies/indicators.py` calcula SQZMOM con Heikin Ashi.
5. `strategies/signals.py` detecta reversiones al cierre.
6. `backtest/engine.py` ejecuta en el open real de la siguiente vela.
7. `backtest/statistics.py` informa métricas globales y mensuales.

El reporte de auditoría distingue siempre `entry_signal_time`/`exit_signal_time`
(velas HA que confirman) de `entry_time`/`exit_time` (velas reales ejecutadas).
Los timestamps se expresan en UTC para compararlos sin ambigüedad.

## Estado y límites

- La fuente en vivo actual es REST; WebSocket queda para una fase posterior.
- El backtest modela comisión, slippage y funding fijo estimado. El funding
  histórico real aún no forma parte del snapshot.
- El criterio 70/30 es provisional y no sustituye expectativa, drawdown o
  significancia estadística.
- El cálculo de riesgo y la persistencia del ciclo están implementados, pero el
  ejecutor, las órdenes protectoras y la reconciliación resolutiva siguen
  pendientes.

## Gestión de riesgo y persistencia — Fase 2

- Sizing por riesgo porcentual con límite nocional y filtros Binance.
- Stop inicial por ATR y disparador de breakeven por múltiplo de R.
- Posición única fail-closed ante exposición o discrepancias.
- Auditoría transaccional de señal, órdenes, fills, stops y cierre.
- P&L neto, curva compuesta, profit factor, max drawdown y Sharpe por trade.
- 23 pruebas offline verificadas.

## Ejecución protegida — Fase 3

- `execution/order_executor.py` procesa entradas, salidas y breakeven.
- `execution/safety.py` mantiene el kill switch de runtime.
- `positions/reconciliation.py` compara Binance con el registro local.
- Los stops condicionales usan Binance Algo y todas las salidas son reduce-only.
- El sistema exige modo One-way antes de cualquier mutación real.
- 33 pruebas offline verifican el flujo y los fallos críticos.
- Todavía no existe un runner autónomo ni se ha ejecutado una integración
  privada contra Testnet; `TRADING_ENABLED` debe permanecer desactivado.

## Runner operativo — Fase 4

- `run_testnet.py` ofrece ciclo único, snapshot offline y polling continuo.
- `processed_cycles` deduplica persistentemente cada vela evaluada.
- `runtime_state` conserva el kill switch entre reinicios.
- ATR de Wilder sobre Heikin Ashi alimenta el stop dinámico.
- Un lock impide runners locales simultáneos.
- La integración real existe pero se omite salvo opt-in explícito.
- La suite normal continúa siendo totalmente offline.

## Infraestructura Testnet — Fase 1

- `config.py` carga y valida el entorno con defaults fail-closed.
- `logs/logger.py` escribe logs UTC rotativos y elimina secretos.
- `exchange/binance_client.py` encapsula USD-M Futures Testnet.
- Cantidades, precios y filtros usan `Decimal` internamente.
- Solo las lecturas tienen backoff automático.
- Una orden incierta se consulta por `clientOrderId` y nunca se reenvía.
- Esta fase no autoriza todavía un ciclo autónomo de paper trading.
