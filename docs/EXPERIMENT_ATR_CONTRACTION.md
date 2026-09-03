# Experimento 001 — Contracción ATR en la entrada

Fecha: 2026-09-03. Estado: **rechazado en desarrollo; no validado fuera de
muestra**.

## Hipótesis y regla pre-registrada

Permitir una entrada sólo cuando, al cierre de su vela de señal:

```text
ATR(14) real / media de ATR(14) de las últimas 20 barras <= 1.0
```

No se exploraron otros umbrales ni longitudes. Las señales de salida permanecen
intactas y la baseline no se modificó. El snapshot ya había sido utilizado para
descubrir la hipótesis; por ello esta ejecución sólo es evidencia de desarrollo.

## Resultado

| Alcance | Trades | Win rate | Expectancy | PF | Suma neta |
|---|---:|---:|---:|---:|---:|
| Baseline total | 100 | 51.0 % | -0.251 % | 0.83 | -25.10 % |
| Filtro total | 49 | 65.3 % | +0.817 % | 2.38 | +40.04 % |
| Filtro LONG | 23 | 65.2 % | +0.364 % | 1.57 | +8.38 % |
| Filtro SHORT | 26 | 65.4 % | +1.218 % | 3.23 | +31.66 % |
| Filtro primera mitad | 25 | 64.0 % | +0.635 % | 1.79 | +15.88 % |
| Filtro segunda mitad | 24 | 66.7 % | +1.006 % | 3.76 | +24.15 % |

El promedio de pérdidas mejora de -3.02 % a -1.70 %. La dirección del efecto es
consistente en ambas mitades cronológicas, pero éstas no son holdouts genuinos:
la hipótesis se seleccionó tras estudiar el dataset completo.

## Criterios de aceptación

| Criterio pre-registrado | Resultado |
|---|---:|
| Mejorar expectancy neta | Cumple |
| Mejorar profit factor neto | Cumple |
| Reducir pérdida media | Cumple |
| Conservar >=70 % de trades | **No cumple: 49.0 %** |
| Conservar >=70 % del PnL positivo | **No cumple: 56.1 %** |
| Validación fuera de muestra | **No realizada** |

## Decisión

La regla exacta se rechaza porque es demasiado restrictiva según los criterios
definidos antes de ejecutarla. No se ajustará el corte usando este snapshot. El
resultado sí conserva la familia de hipótesis —régimen de volatilidad en la
entrada— como candidata para investigación futura, pero cualquier nueva regla
debe formularse por una razón de mercado independiente y probarse primero en un
período no solapado.

Artefactos reproducibles:

- `research/atr_contraction_experiment.py`
- `research/output/atr_contraction_experiment/comparison.csv`
- `research/output/atr_contraction_experiment/entry_audit.csv`
- `research/output/atr_contraction_experiment/summary.json`
- `tests/test_atr_contraction_experiment.py`

Ejecución:

```bash
.venv/bin/python -m research.atr_contraction_experiment
```
