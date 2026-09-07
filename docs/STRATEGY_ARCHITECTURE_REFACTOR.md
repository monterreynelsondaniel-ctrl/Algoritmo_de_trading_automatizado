# Refactor arquitectónico — encapsulación de Strategy 1

Fecha: 2026-09-06.

## A. Auditoría inicial

La rama era `main`, cuatro commits por delante de `origin/main`, con working tree
limpio. El último estado estable era `9cc6fbf`. No había cambios locales del
usuario ni archivos sensibles pendientes.

Se encontraron 47 tests: todos correctos y una integración Binance Testnet
omitida por opt-in. La baseline previa reproducida sobre
`btcusdt_4h_2026_08` fue:

- 176 señales históricas;
- 101 filas de backtest: 100 trades cerrados y uno abierto;
- win rate 51.00 %;
- P&L neto -25.0992807215 %;
- retorno compuesto -30.0154016164 %;
- profit factor 0.8303556087;
- LONG -24.1839326543 %;
- SHORT -0.9153480672 %.

Dependencias encontradas:

```text
strategies/candles.py (Heikin-Ashi compartido)
        ↓
strategies/indicators.py (ATR/BB/KC/SQZMOM/color compartidos)
        ↓
strategies/signals.py (reglas dark/light específicas, antes globales)
        ↓
backtest/run.py ──→ backtest/engine.py (ejecución genérica)
        ↓
run_testnet.py (preparación y señal antes acopladas a imports globales)
```

`backtest/engine.py` ya recibía un DataFrame preparado y una lista de señales;
no contenía reglas SQZMOM. `squeeze_strategy.py` y `confidence.py` son utilidades
históricas no usadas por el flujo baseline. `main.py` y `test_signals.py` son
scripts auxiliares antiguos, no entrypoints operativos.

## B. Decisión arquitectónica

Se eligió una migración mínima:

```text
strategies/candles.py                  compartido
strategies/indicators.py               compartido
strategies/base.py                     contrato mínimo
strategies/registry.py                 selección explícita
strategies/strategy_1/strategy.py      composición Strategy 1
strategies/strategy_1/signals.py       reglas SQZMOM Strategy 1
strategies/signals.py                  fachada compatible temporal
```

Strategy 1 compone las transformaciones e indicadores compartidos y encapsula
únicamente que `dark_red → light_red` significa LONG y
`dark_green → light_green` significa SHORT. El backtest y el runner consumen el
contrato de estrategia e incluyen `strategy_1` como default explícito.

Una futura Strategy 2 podrá reutilizar candles, indicadores, datos, engine,
estadísticas, ejecución y persistencia, e implementar sus propios métodos de
preparación/señal. No se creó Strategy 2 ni directorios vacíos.

Se decidió no crear una jerarquía de clases base, lifecycle framework, sistema
de plugins, configuración multi-timeframe ni registro dinámico. Un `Protocol` y
un registry explícito de una entrada son suficientes hoy.

## C. Archivos modificados

- `backtest/run.py`
- `run_testnet.py`
- `strategies/signals.py`
- `tests/test_runner.py`
- `README.md`
- `estructura.md`
- `docs/PROJECT_CONTEXT.md`
- `docs/DECISIONS.md`
- `docs/NEXT_STEPS.md`

## D. Archivos creados

- `strategies/__init__.py`
- `strategies/base.py`
- `strategies/registry.py`
- `strategies/strategy_1/__init__.py`
- `strategies/strategy_1/signals.py`
- `strategies/strategy_1/strategy.py`
- `tests/test_strategy_1_regression.py`
- `docs/STRATEGY_ARCHITECTURE_REFACTOR.md`

## E. Compatibilidad Strategy 1

| Métrica | PRE | POST confirmado |
|---|---:|---:|
| Señales históricas | 176 | 176 |
| Trades cerrados | 100 | 100 |
| Trade abierto final | 1 | 1 |
| Win rate | 51.00 % | 51.00 % |
| P&L neto | -25.0992807215 % | -25.0992807215 % |
| Retorno compuesto | -30.0154016164 % | -30.0154016164 % |
| Profit factor | 0.8303556087 | 0.8303556087 |
| LONG | -24.1839326543 % | -24.1839326543 % |
| SHORT | -0.9153480672 % | -0.9153480672 % |

El test de regresión congela fingerprints de todas las señales y de todos los
trades, incluidos timestamps, direcciones, precios de ejecución y PnL. La
validación final confirmó que PRE y POST son idénticos.

## F. Tests

Se añadió cobertura para secuencia/fingerprint de señales y trades, métricas
fundamentales, selección de estrategia e inyección en el runner. La suite final
ejecutó 51 tests correctamente y omitió una integración Testnet por opt-in.

## G. Riesgos y deuda técnica

- `strategies/signals.py` es una fachada de compatibilidad; retirarla requiere
  migrar primero scripts externos o antiguos.
- `main.py` duplica una implementación Heikin-Ashi histórica y debería
  clasificarse o retirarse en otra tarea, no dentro de esta migración.
- `squeeze_strategy.py` y `confidence.py` no forman parte del flujo activo; antes
  de reutilizarlos debe decidirse si son interpretación compartida o reglas.
- El contrato usa DataFrames y diccionarios sin modelos tipados de señal. Añadir
  modelos ahora sería abstracción prematura y una migración de mayor riesgo.
- Strategy 2 necesitará resolver explícitamente sincronización multi-timeframe;
  esa responsabilidad no debe incorporarse al engine sin requisitos concretos.

## H. Estado Git final

No se crea commit automáticamente. El estado exacto se registra en la entrega
después de tests, backtest, revisión de snapshots e imports.
