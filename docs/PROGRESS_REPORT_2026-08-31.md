# Informe de progreso del proyecto

**Fecha de corte:** 2026-08-31  
**Proyecto:** Trading bot SQZMOM para Binance USD-M Futures  
**Estado:** Backtest reproducible completado; infraestructura Testnet Fase 1 completada

## 1. Resumen ejecutivo

El proyecto comenzó como un prototipo que descargaba velas desde Binance,
calculaba SQZMOM y mostraba reversiones. El código contenía una separación
inicial por módulos, pero todavía no era posible considerar sus resultados como
un backtest confiable: no existían pruebas automatizadas, se incluía
potencialmente la vela abierta, la ejecución ocurría en el mismo cierre que
confirmaba la señal y los datos no estaban congelados.

Actualmente se dispone de:

- Un flujo reproducible con 2.199 velas cerradas de BTCUSDT 4h.
- Indicadores calculados sobre velas Heikin Ashi.
- Ejecuciones simuladas al `open` real de la vela posterior a la señal.
- Auditoría individual de entradas y salidas para comparar con TradingView.
- Estadísticas globales y evaluación mensual del criterio 70/30.
- Datos congelados independientes de Binance.
- Configuración segura, logging sanitizado y adaptador Binance USD-M Futures
  Testnet con comportamiento fail-closed.
- Quince pruebas automatizadas sin conexión a internet.

La infraestructura de análisis funciona, pero la estrategia actual **todavía no
cumple el objetivo 70/30 mensual ni está lista para operar autónomamente**.

## 2. Estado inicial encontrado

La revisión inicial identificó los siguientes problemas:

1. `test_signals.py` era un script conectado a Binance, no una prueba
   automatizada con aserciones.
2. El entorno no incluía `pytest` ni un archivo formal de dependencias.
3. El motor entraba al cierre de la misma vela que confirmaba la señal,
   introduciendo un precio de ejecución no garantizado.
4. La descarga podía incluir una vela aún abierta.
5. Pandas calculaba la desviación estándar muestral, diferente de la desviación
   poblacional utilizada para reproducir Pine/TradingView.
6. Heikin Ashi estaba implementado en `main.py`, pero la estrategia histórica
   utilizaba OHLC normal.
7. El P&L total era una suma de porcentajes y no una curva compuesta.
8. No existían comisiones, slippage, funding, drawdown ni gestión de capital.
9. La duración estaba fijada directamente a cuatro horas dentro del motor.
10. Configuración, base de datos, posiciones y logs estaban incompletos o
    desconectados del flujo.

### Primer resultado diagnóstico

Antes de corregir los supuestos se ejecutó una prueba preliminar con 2.200
velas. Produjo 98 operaciones, 57,14 % de aciertos y −15,82 % mediante suma
simple. Este resultado fue útil para detectar problemas, pero quedó obsoleto y
no debe compararse directamente con el backtest vigente porque aún no aplicaba
Heikin Ashi de forma consistente ni entrada en la vela siguiente.

## 3. Decisiones funcionales adoptadas

### Velas e indicadores

- Las señales se calculan sobre OHLC Heikin Ashi.
- Se conserva en paralelo el OHLC real del mercado.
- Los precios sintéticos Heikin Ashi nunca se usan como precios ejecutados.
- Bollinger utiliza desviación estándar poblacional (`ddof=0`).

### Señales y ejecución

- La regla vigente de entrada LONG es `dark_red -> light_red`.
- La regla vigente de entrada SHORT es `dark_green -> light_green`.
- La señal queda confirmada al cierre de su vela.
- La entrada ocurre al `open` real de la vela siguiente.
- Por ahora una señal contraria cierra la posición y abre la inversa en el mismo
  `open` real posterior a la confirmación.
- Una señal en la última vela del dataset no puede ejecutarse.

### Evaluación inicial

- El criterio provisional es un win rate mensual mínimo de 70 %.
- Las operaciones se asignan al mes UTC de su salida.
- Los breakeven cuentan como operaciones no ganadoras.
- El win rate se conserva como criterio inicial, pero no se considera suficiente
  sin P&L, magnitud de pérdidas y tamaño de muestra.

## 4. Infraestructura de backtesting completada

### Datos reproducibles

Se creó `data/frozen_market_data.py`, que permite guardar snapshots CSV junto
con metadatos JSON y evita sobrescrituras accidentales. La fuente REST de
Binance permanece separada en `exchange/market_data.py` para futuras descargas.

Dataset oficial actual:

| Campo | Valor |
|---|---:|
| Snapshot | `btcusdt_4h_2026_08` |
| Símbolo | BTCUSDT |
| Mercado | Binance Futures |
| Temporalidad | 4h |
| Velas cerradas | 2.199 |
| Primera vela | 2025-08-27 12:00 UTC |
| Última vela | 2026-08-28 20:00 UTC |

### Auditoría de operaciones

El reporte distingue cuatro timestamps:

- `entry_signal_time`: vela HA que confirmó la entrada.
- `entry_time`: vela siguiente, cuyo `open` real se usa como entrada.
- `exit_signal_time`: vela HA que confirmó la salida.
- `exit_time`: vela siguiente, cuyo `open` real se usa como salida.

También registra SQZMOM, transición de color, OHLC Heikin Ashi, precios reales,
MFE, MAE, duración y resultado. Puede exportarse como CSV para revisión manual
contra TradingView.

## 5. Resultado vigente del backtest

Ejecución reproducible realizada el 2026-08-31:

```bash
.venv/bin/python -m backtest.run \
  --snapshot btcusdt_4h_2026_08 \
  --summary-only
```

### Estadísticas globales

| Métrica | Resultado |
|---|---:|
| Operaciones cerradas | 100 |
| Ganadoras | 55 |
| Perdedoras | 45 |
| Win rate | 55,00 % |
| P&L por suma simple | +3,36 % |
| Retorno compuesto | −6,72 % |
| Profit factor | 1,03 |
| P&L promedio | +0,03 % |
| Mejor operación | +13,38 % |
| Peor operación | −23,55 % |
| MFE promedio | +3,10 % |
| MAE promedio | −3,35 % |
| Duración promedio | 85,96 horas |

La diferencia entre la suma positiva y el retorno compuesto negativo se debe a
la secuencia y magnitud de retornos: las pérdidas porcentuales grandes requieren
ganancias proporcionalmente mayores para recuperar capital.

### Resultado por dirección

| Dirección | Operaciones | Win rate | P&L simple |
|---|---:|---:|---:|
| LONG | 50 | 52,00 % | −10,13 % |
| SHORT | 50 | 58,00 % | +13,49 % |

El lado SHORT se comportó mejor. El lado LONG continúa siendo el principal
componente negativo.

### Evaluación mensual 70/30

| Mes UTC | Trades | Wins | Losses | Win rate | P&L | Cumple |
|---|---:|---:|---:|---:|---:|:---:|
| 2025-09 | 6 | 3 | 3 | 50,00 % | −5,43 % | No |
| 2025-10 | 7 | 4 | 3 | 57,14 % | −5,63 % | No |
| 2025-11 | 5 | 1 | 4 | 20,00 % | −15,25 % | No |
| 2025-12 | 11 | 5 | 6 | 45,45 % | +2,85 % | No |
| 2026-01 | 7 | 3 | 4 | 42,86 % | −7,29 % | No |
| 2026-02 | 8 | 6 | 2 | 75,00 % | +18,92 % | Sí |
| 2026-03 | 10 | 5 | 5 | 50,00 % | +11,19 % | No |
| 2026-04 | 9 | 6 | 3 | 66,67 % | +0,61 % | No |
| 2026-05 | 10 | 5 | 5 | 50,00 % | +3,28 % | No |
| 2026-06 | 9 | 7 | 2 | 77,78 % | +17,42 % | Sí |
| 2026-07 | 12 | 5 | 7 | 41,67 % | +3,00 % | No |
| 2026-08 | 6 | 5 | 1 | 83,33 % | −20,31 % | Sí |

Solo 3 de 12 meses cumplen el criterio. Agosto demuestra la limitación del win
rate aislado: alcanzó 83,33 %, pero una pérdida grande llevó el mes a −20,31 %.

### Conclusión sobre la estrategia

La estrategia se ejecuta de manera coherente con las reglas acordadas y el
resultado es reproducible. Sin embargo, **su desempeño actual no satisface las
expectativas**:

- Win rate global inferior al 70 %.
- Solo 25 % de los meses cumple 70/30.
- Retorno compuesto negativo.
- Profit factor apenas superior a uno antes de costes.
- Riesgo de cola elevado por una peor operación de −23,55 %.
- El lado LONG presenta resultado negativo.

Agregar comisiones, slippage y funding probablemente empeorará estas métricas.
Por ello, “el código corre correctamente” no significa que “la estrategia sea
rentable”.

## 6. Fase 1 de Binance Testnet completada

### Configuración segura

- Variables cargadas con `python-dotenv`.
- Separación Testnet/live y credenciales independientes.
- Defaults `TRADING_ENABLED=false` y `DRY_RUN=true`.
- Validación fail-closed de tipos, rangos y entorno.
- `.env.example` documentado y `.env` ignorado.
- `can_send_orders()` exige trading habilitado, dry-run desactivado y
  credenciales del entorno seleccionado.

### Logging

- Timestamps UTC.
- Rotación de 5 MB y tres backups.
- Nivel configurable.
- Sanitización recursiva de API keys, secretos, firmas, autorización, Bearer
  tokens, diccionarios anidados y JSON crudo.
- Prevención de handlers duplicados.

### Adaptador USD-M Futures

Se implementaron consultas para balance disponible USDT, mark price, posiciones,
órdenes abiertas y filtros del símbolo, además de leverage y creación de orden.

Características de seguridad:

- `Decimal` para cantidades, precios y filtros.
- Normalización por `stepSize` y `tickSize`.
- Validación de `MIN_NOTIONAL`.
- Caché de `exchangeInfo`.
- Máximo tres intentos con backoff solo para lecturas idempotentes.
- `clientOrderId` obligatorio o generado automáticamente.
- Ningún reenvío ciego tras timeout.
- Consulta de la orden original después de un resultado incierto.
- `BinanceUnknownOrderStateError` cuando no puede confirmarse el estado.
- Mutaciones simuladas sin red en `DRY_RUN`.

### Estado seguro verificado

```text
BINANCE_ENV=testnet
TRADING_ENABLED=false
DRY_RUN=true
has_credentials=false
can_send_orders=false
```

No se enviaron órdenes ni se realizaron llamadas privadas durante esta fase.

## 7. Calidad y pruebas

La suite actual contiene 15 pruebas y se ejecuta completamente offline:

- Transformación Heikin Ashi preservando precios reales.
- Entrada y salida en la vela siguiente.
- Rechazo de una señal no ejecutable en la última vela.
- Round-trip y protección de snapshots.
- Criterio mensual 70/30.
- Configuración fail-closed y validación de booleanos.
- Preparación segura para live.
- Normalización decimal y caché de filtros.
- Validación de mínimo nocional.
- Backoff de lecturas.
- Timeout de orden sin duplicación.
- Estado de orden desconocido.
- Dry-run sin llamadas al exchange.
- Sanitización de credenciales y JSON.

Resultado verificado el 2026-08-31:

```text
Ran 15 tests
OK
```

## 8. Elementos pendientes antes de Paper Trading autónomo

La Fase 1 no completa todavía un bot operativo. Faltan:

1. Gestión de riesgo y tamaño de posición.
2. Estado de posición única y reconciliación con Binance.
3. Stop ATR para LONG y SHORT.
4. Movimiento del stop a breakeven.
5. Órdenes de protección `reduceOnly`.
6. Persistencia completa de órdenes, fills, stops y cierres.
7. Comisiones, slippage y funding en backtest.
8. Definición final de la condición de cierre.
9. Ejecutor de órdenes y kill switch.
10. Prueba de integración opt-in contra Futures Testnet.
11. Comparación vela por vela de SQZMOM contra el Pine Script original.

## 9. Recomendación para la siguiente fase

Continuar con gestión de riesgo y posición única, manteniendo:

- Binance como fuente de verdad.
- Una sola posición y un solo símbolo en el MVP.
- Riesgo porcentual pequeño y límite nocional.
- `DRY_RUN=true` hasta completar reconciliación, stops y pruebas.
- Pruebas offline antes de cualquier integración real.

No se recomienda activar `TRADING_ENABLED` todavía.

## 10. Archivos principales

- `backtest/run.py`: orquestación reproducible.
- `backtest/engine.py`: ejecución y auditoría de trades.
- `backtest/statistics.py`: métricas globales y mensuales.
- `data/frozen_market_data.py`: snapshots históricos.
- `strategies/candles.py`: transformación Heikin Ashi.
- `strategies/indicators.py`: SQZMOM y canales.
- `strategies/signals.py`: reglas LONG/SHORT.
- `config.py`: configuración segura.
- `logs/logger.py`: logging sanitizado.
- `exchange/binance_client.py`: adaptador Futures Testnet.
- `exchange/exceptions.py`: errores de dominio.
- `tests/`: suite automatizada offline.

Este documento representa el estado verificable del proyecto al cierre de la
Fase 1 y debe actualizarse al terminar cada fase posterior.
