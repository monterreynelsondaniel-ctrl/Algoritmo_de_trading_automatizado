# Reporte de Fase 2

## Alcance completado

- Modelo `Trade` extendido para auditar señal, órdenes, fills, stops, riesgo,
  comisiones, estado, cierre y reconciliación.
- Servicio transaccional con rollback y cierre garantizado de sesiones.
- Motor de riesgo con posición única fail-closed, sizing porcentual, límite
  nocional, filtros Binance, stop ATR y breakeven a múltiplos de R.
- Backtest con comisión por lado, slippage adverso, funding fijo estimado, P&L
  bruto/neto, curva compuesta, profit factor, drawdown y Sharpe por trade.
- 23 pruebas unitarias offline.

## Resultado del snapshot con fricciones predeterminadas

Snapshot: `btcusdt_4h_2026_08`, 100 operaciones cerradas.

| Métrica | Resultado |
|---|---:|
| Win rate neto | 51,00 % |
| P&L bruto simple | +3,36 % |
| P&L neto simple | −25,10 % |
| Retorno compuesto | −30,02 % |
| Comisiones + funding estimado | 18,48 % |
| Slippage estimado | 9,98 % |
| Profit factor | 0,83 |
| Max drawdown | 37,07 % |
| Sharpe por operación | −0,56 |
| LONG neto | −24,18 % |
| SHORT neto | −0,92 % |

Solo febrero de 2026 conserva el criterio mensual 70/30 después de fricciones.
La estrategia vigente no es apta para producción y el trading sigue bloqueado.

## Límites conscientes

- El funding es fijo y conservador; no proviene de eventos históricos reales.
- No se han implementado aún órdenes stop en Binance ni reconciliación capaz de
  resolver automáticamente discrepancias.
- El esquema antiguo no se transforma automáticamente: cualquier base previa
  valiosa requiere una migración explícita antes de operar.
- Sharpe usa retornos por operación y no está anualizado por calendario.
