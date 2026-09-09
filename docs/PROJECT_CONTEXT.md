# Contexto del proyecto

## Objetivo actual

Validar Strategy 1, una estrategia sencilla de reversión SQZMOM sobre futuros BTCUSDT en
temporalidad de cuatro horas. El criterio preliminar es alcanzar al menos 70 %
de operaciones ganadoras en cada mes evaluado.

## Flujo de datos

1. `exchange/market_data.py` obtiene velas cerradas desde Binance REST.
2. `data/frozen_market_data.py` guarda y recupera snapshots reproducibles.
3. `strategies/candles.py` y `strategies/indicators.py` proveen cálculos compartidos.
4. `strategies/strategy_1/` prepara HA/SQZMOM e interpreta sus reversiones.
5. `strategies/registry.py` entrega la estrategia seleccionada al consumidor.
6. `backtest/engine.py` ejecuta señales genéricas en el open real siguiente.
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
- La investigación cuantitativa reproducible del snapshot actual está en
  `docs/QUANTITATIVE_RESEARCH_BASELINE.md`. La baseline neta es -25.10 %, PF
  0.83 y 51 % de acierto; ninguna hipótesis exploratoria es aún una regla.
- El primer experimento pre-registrado de contracción ATR mejoró métricas dentro
  de muestra, pero fue rechazado por retener sólo 49 % de trades y 56 % del PnL
  positivo. Véase `docs/EXPERIMENT_ATR_CONTRACTION.md`.
- El análisis posterior de dinámica ATR descartó un filtro simétrico: la
  expansión previa deteriora consistentemente LONG, pero no SHORT. Es una
  hipótesis de desarrollo, no una regla ni validación fuera de muestra.
- El experimento DMI/ADX rechazó la hipótesis general de que ADX alto empeora
  reversals counter-trend. La alineación DMI sí fue prometedora sólo en SHORT;
  permanece exploratoria y no se incorporó como filtro.
- El cálculo de riesgo, persistencia, ejecución protegida, reconciliación y
  runner polling están implementados; la integración Testnet sigue pendiente.
- La estrategia histórica está encapsulada como `strategy_1`. Su baseline y
  secuencia completa están protegidas mediante regresión.
- Strategy 2 existe únicamente como arquitectura experimental: tendencia 1D,
  setup 4H, confirmación posterior 1H, revisión AI de entrada y gestión 4H.
  Aún no hay bundle histórico 1D/4H/1H, cache real ni resultados cuantitativos.
- `exchange/multi_timeframe.py` impide exponer velas cuyo `close_time` aún no
  ocurrió. Los snapshots simples se pueden componer mediante manifests bundle.
- Las decisiones AI usan Responses API, JSON Schema estricto, validación local,
  cache SQLite y auditoría. Replay es el default; un cache miss impide el
  backtest Strategy 2 en lugar de aprobar silenciosamente.
- El modelo research predeterminado es `gpt-5.6-terra`; Sol/Luna se seleccionan
  por configuración para comparaciones que mantienen caches independientes.
- El primer bundle Strategy 2, `btcusdt_1d_4h_1h_2026_08`, está preparado
  localmente y documentado en `STRATEGY_2_FROZEN_DATASET.md`. Reutiliza el 4H
  histórico intacto; su incorporación a Git espera aprobación del allowlist.

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
