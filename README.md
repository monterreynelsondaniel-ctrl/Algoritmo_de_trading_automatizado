# Trading Bot — arquitectura multi-estrategia

La estrategia histórica se denomina **Strategy 1**: reversión SQZMOM para
futuros BTCUSDT.
Las señales se calculan con velas Heikin Ashi y las órdenes se simulan en el
`open` real de la vela posterior a la confirmación.

> **Estado:** MVP preparado para validación manual en Binance USD-M Futures
> Testnet. No está autorizado ni validado para operar con dinero real. La
> estrategia actual presenta rendimiento neto negativo en el snapshot oficial.

## Instalación

Requiere Python 3.10 o posterior:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

## Uso reproducible

Congelar velas cerradas desde Binance y ejecutar el backtest:

```bash
.venv/bin/python -m backtest.run --download --save-as btcusdt_4h_2026_08 --limit 2200
```

Repetir el backtest sin depender de Binance:

```bash
.venv/bin/python -m backtest.run --snapshot btcusdt_4h_2026_08
```

Strategy 1 es el default. También puede seleccionarse explícitamente:

```bash
.venv/bin/python -m backtest.run \
  --snapshot btcusdt_4h_2026_08 --strategy strategy_1
```

El reporte muestra por defecto, para cada operación, la vela Heikin Ashi que
confirmó la señal y la vela siguiente donde se ejecutó al `open` real. Todas las
horas se imprimen en UTC. Para exportar todas las columnas (incluidos OHLC
Heikin Ashi y SQZMOM de las señales):

```bash
.venv/bin/python -m backtest.run \
  --snapshot btcusdt_4h_2026_08 \
  --trades-csv backtest_trades.csv
```

Usa `--summary-only` cuando no necesites el detalle individual.

El backtest incluye por defecto comisión taker de 0,04 % por lado, slippage de
0,05 % por ejecución y una estimación conservadora de funding de 0,01 % por
cada intervalo completo de ocho horas. Pueden ajustarse con:

```bash
--commission-rate 0.0004 --slippage-rate 0.0005 \
--funding-rate 0.0001 --funding-interval-hours 8
```

El funding histórico real todavía no forma parte del snapshot; el valor actual
es una estimación fija, no una reproducción de pagos reales de Binance.

## Ejecución protegida

Las Fases 3 y 4 añaden `OrderExecutor`, reconciliación, stops Algo reduce-only,
kill switch persistente y runner por polling. No se han ejecutado todavía
órdenes privadas en Testnet. Consulta `docs/PHASE_4_REPORT.md` antes de habilitar
la integración.

## Runner de polling

Preparar configuración:

```bash
cp .env.example .env
```

Validación completamente offline con el snapshot congelado:

```bash
.venv/bin/python run_testnet.py \
  --snapshot btcusdt_4h_2026_08 --strategy strategy_1
```

Un ciclo con datos públicos recientes, manteniendo simulación:

```bash
.venv/bin/python run_testnet.py --once
```

Polling continuo cada 60 segundos:

```bash
.venv/bin/python run_testnet.py --poll-seconds 60
```

El runner procesa únicamente velas cerradas, registra incluso ciclos sin señal,
deduplica por símbolo/timeframe/timestamp y evita dos procesos locales mediante
un lock. Una señal opuesta cierra la posición pero no revierte dentro del mismo
ciclo. No existe trailing stop; solo stop ATR y breakeven a 1,5 R.

## Pruebas

Suite offline:

```bash
.venv/bin/python -m unittest discover -v
```

La integración privada está omitida por defecto. Antes de habilitarla, utiliza
una cuenta Futures Testnet exclusivamente dedicada y neutral, configura sus
credenciales, `TRADING_ENABLED=true`, `DRY_RUN=false` y un nocional pequeño:

```bash
RUN_BINANCE_INTEGRATION=1 \
.venv/bin/python -m unittest tests.test_binance_integration -v
```

La prueba se niega a comenzar si encuentra posiciones u órdenes previas y solo
cancela el stop creado por ella. Si la red falla durante `finally`, puede ser
necesaria una revisión manual de la cuenta Testnet.

Los snapshots se guardan en `data/snapshots/` como CSV más metadatos JSON y no
se sobrescriben salvo que se solicite explícitamente desde código.

Consulta `docs/PROJECT_CONTEXT.md` y `docs/DECISIONS.md` antes de cambiar reglas.
El historial consolidado hasta la Fase 1 está en
`docs/PROGRESS_REPORT_2026-08-31.md`.

## Estrategias

`strategies/candles.py` y `strategies/indicators.py` son reutilizables. Las
reglas de Strategy 1 están encapsuladas en `strategies/strategy_1/`. El backtest
y el runner dependen del contrato mínimo de `strategies/base.py`, no de reglas
SQZMOM concretas. Una futura Strategy 2 deberá implementar ese contrato y
registrarse explícitamente; Strategy 2 todavía no existe.

## Seguridad y Binance Futures

La Fase 1 incorpora configuración fail-closed, logging sanitizado y el adaptador
REST de Binance USD-M Futures. Copia `.env.example` a `.env` y completa solo las
credenciales de Testnet. Por defecto:

```text
TRADING_ENABLED=false
DRY_RUN=true
```

En ese estado ninguna mutación llega a Binance. El adaptador acepta un cliente
inyectado para pruebas, reintenta únicamente lecturas y nunca reenvía a ciegas
una orden cuyo resultado sea incierto.
