# Dataset congelado multi-timeframe de Strategy 2

Fecha de creación: 2026-09-09. Estado: datos preparados localmente; todavía no
añadidos a Git.

## Identidad

- Bundle: `btcusdt_1d_4h_1h_2026_08`
- Símbolo: BTCUSDT USD-M Futures
- Timeframes: 1D, 4H y 1H
- Evaluation start: `2025-09-05T16:00:00+00:00`
- Evaluation end: `2026-08-29T00:00:00+00:00`
- Velas: OHLCV raw de Binance; indicadores no persistidos
- Close time: último milisegundo incluido
- Event time: `close_time + 1 ms`

## Componentes

| Timeframe | Snapshot | Rows | First open | Last close | Source |
|---|---|---:|---|---|---|
| 1D | `btcusdt_1d_2026_08` | 413 | 2025-07-12 00:00 UTC | 2026-08-28 23:59:59.999 UTC | Binance Futures REST |
| 4H | `btcusdt_4h_2026_08` | 2,199 | 2025-08-27 12:00 UTC | 2026-08-28 23:59:59.999 UTC | Snapshot Strategy 1 reutilizado |
| 1H | `btcusdt_1h_2026_08` | 8,796 | 2025-08-27 12:00 UTC | 2026-08-28 23:59:59.999 UTC | Binance Futures REST |

El componente 4H conserva sus hashes originales:

- CSV: `3000e5fe151ee403f2828361b76b1f333273144653a10c8e5d2057e380089384`
- JSON: `d95f80d54d542bd43a2acac653ee47b8c28fd0babb3289df410034d21a07ee5b`

## Warm-up

EMA55 necesita 55 observaciones y domina ATR14 (14), Disparity20 (20),
DMI/ADX14 (aproximadamente 28) y SQZMOM/color (aproximadamente 40). El ancla 4H
alcanza su fila 55 al cierre del 5 de septiembre de 2025 a las 16:00 UTC.

En ese evento existen exactamente 55 velas diarias cerradas desde el 12 de
julio, 55 velas 4H y 220 velas 1H. Los indicadores requeridos por cada etapa
están inicializados. El período anterior es data warm-up y no evaluation.

## Integridad

Los tres componentes tienen:

- cero timestamps duplicados;
- cero gaps de 1D/4H/1H;
- cero nulls en todas las columnas;
- ordering cronológico estricto;
- cero violaciones OHLC;
- cero errores de boundary;
- último cierre común en `2026-08-28 23:59:59.999 UTC`.

No se rellenaron, corrigieron ni interpolaron datos.

## Reproducción offline

```python
from data.frozen_market_data import FrozenMarketDataStore
from strategies.strategy_2 import Strategy2

store = FrozenMarketDataStore()
market = store.load_bundle("btcusdt_1d_4h_1h_2026_08")
prepared = Strategy2().prepare_market_data(market)
```

La carga desde disco produjo 8,842 eventos causales totales y 8,577 dentro del
rango de evaluación. Un smoke test alcanzó el primer candidate después de 50
eventos evaluables; se detuvo sin aprobar/rechazarlo y sin llamadas OpenAI.

## Política de versionado pendiente

Los nuevos CSV/JSON/bundle suman aproximadamente 1.39 MB y no requieren Git LFS
por tamaño. Sin embargo, `.gitignore` permite actualmente sólo el snapshot 4H
histórico. Antes del commit de datos se debe aprobar un allowlist explícito para
los cinco archivos nuevos; no se debe abrir un wildcard para futuros snapshots.
