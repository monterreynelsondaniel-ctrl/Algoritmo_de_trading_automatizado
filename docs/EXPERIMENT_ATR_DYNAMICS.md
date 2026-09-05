# Experimento 002 — Dinámica inmediata del ATR

Fecha: 2026-09-05. Estado: **hipótesis general rechazada; línea LONG aceptada
para diseñar un experimento posterior**.

## Diseño

Se midió, sin modificar la estrategia:

```text
atr_change_N = ATR(14) señal / ATR(14) hace N velas - 1
N = 1, 2, 3
```

ATR usa OHLC real y Wilder RMA. Todo se calcula al cierre de la vela de señal.
`EXPANDING` significa cambio positivo y `CONTRACTING` negativo; no hubo valores
exactamente sin cambio. También se dividió cada cambio en tercios de igual tamaño
para comprobar forma/monotonicidad, sin convertir sus límites en thresholds.

El análisis es de desarrollo sobre el mismo snapshot empleado para descubrir la
familia ATR. No es validación fuera de muestra ni prueba de causalidad.

## Resultado combinado

| Ventana | Dirección | N | Expectancy | PF | MAE medio | Pérdidas <-3 % | Worst |
|---|---|---:|---:|---:|---:|---:|---:|
| 1 vela | Contracción | 55 | -0.02 % | 0.98 | -3.15 % | 10.9 % | -15.61 % |
| 1 vela | Expansión | 45 | -0.53 % | 0.72 | -3.70 % | 15.6 % | -24.02 % |
| 2 velas | Contracción | 55 | -0.22 % | 0.81 | -3.35 % | 7.3 % | -24.02 % |
| 2 velas | Expansión | 45 | -0.29 % | 0.84 | -3.45 % | 20.0 % | -15.61 % |
| 3 velas | Contracción | 55 | -0.33 % | 0.73 | -3.47 % | 9.1 % | -24.02 % |
| 3 velas | Expansión | 45 | -0.15 % | 0.91 | -3.31 % | 17.8 % | -15.61 % |

La frecuencia de pérdidas grandes aumenta con expansión en las tres ventanas,
pero expectancy, PF, MAE y worst no se deterioran consistentemente. Los tercios
tampoco forman una relación monotónica: en una vela el tercio medio fue el peor,
no el superior. Al retirar los peores uno y dos trades, el signo combinado de la
diferencia de expectancy cambia según ventana. La hipótesis combinada falla.

## LONG

| Ventana | Expectancy contracción / expansión | PF contracción / expansión | MAE contracción / expansión | Frecuencia <-3 % contracción / expansión |
|---|---:|---:|---:|---:|
| 1 vela | -0.17 / -0.89 % | 0.88 / 0.42 | -3.37 / -3.42 % | 10.7 / 13.6 % |
| 2 velas | -0.21 / -0.84 % | 0.80 / 0.57 | -2.90 / -4.01 % | 10.7 / 13.6 % |
| 3 velas | -0.14 / -0.92 % | 0.85 / 0.57 | -2.81 / -4.13 % | 7.1 / 18.2 % |

LONG sí presenta deterioro con expansión en las cuatro dimensiones y las tres
ventanas. Tras retirar los dos peores LONG, la diferencia de expectancy
expansión menos contracción permanece negativa: -1.72, -0.31 y -0.47 puntos para
1, 2 y 3 velas. Al retirar sólo el peor, la ventana de dos velas queda casi
neutral (+0.07), señal de incertidumbre. El worst tampoco empeora en la ventana
de una vela. La evidencia es interesante, no concluyente.

## SHORT

En una vela, expansión fue peor (expectancy -0.19 % frente a +0.13 %). En dos y
tres velas ocurrió lo contrario: +0.24 % frente a -0.24 %, y +0.59 % frente a
-0.53 %. El efecto cambia también entre mitades temporales y al retirar outliers.
Aunque la expansión mostró más pérdidas <-3 %, también retuvo ganancias grandes,
por lo que usarla como bloqueo SHORT no está respaldado.

## Evaluación contra los criterios

- **Expectancy/PF:** consistentes únicamente en LONG.
- **MAE:** consistente en LONG, casi nulo a una vela y claro a 2–3.
- **Pérdidas grandes:** mayor frecuencia con expansión en todos los lados y
  ventanas, pero no implica peor expectancy en SHORT.
- **Worst trade:** no consistente; los extremos cambian de grupo por ventana.
- **Outliers:** la conclusión combinada no es robusta. La señal LONG conserva
  dirección general al retirar dos extremos, con una excepción casi neutral al
  retirar uno.
- **Estabilidad temporal:** insuficiente para declarar edge; primera y segunda
  mitad discrepan en varios contrastes.

## Decisión metodológica

Se descarta la hipótesis de un filtro simétrico LONG/SHORT y no se cambia la
estrategia. Se acepta únicamente que la expansión previa del ATR merece un
experimento futuro específico para LONG. Antes de ejecutarlo debe pre-registrarse
una sola ventana/regla y reservarse un snapshot no solapado. Elegir ahora entre
1, 2 o 3 velas usando el mejor P&L introduciría selección retrospectiva.

El siguiente candidato independiente continúa siendo fuerza de tendencia/ADX,
pero no debe mezclarse con ATR en el mismo experimento.

## Reproducibilidad

```bash
.venv/bin/python -m research.atr_dynamics_analysis
```

Artefactos:

- `research/atr_dynamics_analysis.py`
- `research/output/atr_dynamics_analysis/trade_audit.csv`
- `research/output/atr_dynamics_analysis/grouped_metrics.csv`
- `research/output/atr_dynamics_analysis/outlier_robustness.csv`
- `research/output/atr_dynamics_analysis/summary.json`
- `tests/test_atr_dynamics_analysis.py`
