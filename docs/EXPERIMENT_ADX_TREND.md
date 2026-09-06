# Experimento 003 — Fuerza de tendencia mediante DMI/ADX

Fecha: 2026-09-06. Clasificación: **EXPLORATORY / IN-SAMPLE**.

## 1. Hipótesis

Los reversals SQZMOM contra la dirección DMI dominante deberían rendir peor
cuando ADX todavía es alto. No se presupuso simetría entre LONG y SHORT.

## 2. Diseño

Se conservaron exactamente las 100 operaciones cerradas de la estrategia. ADX
no filtra ni altera entradas/salidas. SQZMOM continúa sobre Heikin-Ashi; DMI/ADX
se calcula sobre OHLC real. Cada clasificación usa sólo información conocida al
cierre de la vela de señal. El snapshot ya fue usado para descubrimiento, por lo
que ningún resultado es validación fuera de muestra.

## 3. Baseline

La ejecución reproducible coincide con la referencia: 100 trades, 51 % win
rate, -25.10 % neto, -30.02 % compuesto y PF 0.83. LONG suma -24.18 % y SHORT
-0.92 %. No hubo diferencias de baseline.

## 4. ADX/DMI methodology

Se implementaron +DI(14), -DI(14), DX y ADX(14) estándar con Wilder RMA: semilla
SMA de 14 valores y recurrencia `(previo*13 + actual)/14`. Dirección:
`+DI > -DI` alcista y `-DI > +DI` bajista. LONG es aligned con dirección alcista;
SHORT con bajista. No hubo empates DMI ni cambios ADX exactamente cero.

Los terciles globales contienen 33/33/34 trades: LOW hasta ADX 19.76, MID hasta
27.84 y HIGH por encima. Estos límites describen esta muestra; no son reglas ni
thresholds candidatos.

## 5. Aligned vs Counter-trend

| Grupo | N | WR | Expectancy | PF | Mediana | Avg win/loss | Payoff | MFE/MAE | <-3 % / <-5 % | Best/Worst | Duración |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Aligned | 44 | 50.0 % | -0.20 % | 0.86 | +0.03 % | +2.56/-2.97 % | 0.86 | +3.14/-3.27 % | 15.9/9.1 % | +13.12/-15.61 % | 80.8h |
| Counter | 56 | 51.8 % | -0.29 % | 0.80 | +0.15 % | +2.29/-3.06 % | 0.75 | +2.99/-3.49 % | 10.7/7.1 % | +6.64/-24.02 % | 90.0h |

La diferencia combinada es pequeña y contradictoria: counter tiene expectancy,
PF, payoff, MAE y worst algo peores, pero menos pérdidas grandes y mayor win
rate. No constituye evidencia general.

## 6. ADX strength

| Tercio | N | WR | Expectancy | PF | Mediana | MFE/MAE | <-3 % / <-5 % | Worst |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LOW | 33 | 54.5 % | -0.36 % | 0.76 | +0.29 % | +2.76/-3.44 % | 15.2/6.1 % | -15.61 % |
| MID | 33 | 51.5 % | -0.47 % | 0.72 | +0.06 % | +3.01/-3.04 % | 15.2/9.1 % | -24.02 % |
| HIGH | 34 | 47.1 % | +0.07 % | 1.06 | -0.10 % | +3.37/-3.71 % | 8.8/8.8 % | -10.53 % |

No existe deterioro monotónico con ADX: HIGH tiene el mejor expectancy/PF y
menor frecuencia <-3 %, aunque peor MAE que MID. LONG sigue patrón irregular
(LOW -1.07, MID +0.14, HIGH -0.55 %); SHORT mejora de MID -1.06 a HIGH +0.86 %.
No hay evidencia para convertir la fuerza ADX aislada en filtro.

## 7. Trend direction × ADX strength

| Grupo | N | Expectancy | PF | MAE | <-3 % | Worst |
|---|---:|---:|---:|---:|---:|---:|
| Aligned + LOW | 17 | -1.58 % | 0.34 | -4.30 % | 29.4 % | -15.61 % |
| Aligned + MID | 13 | +0.36 % | 1.39 | -2.12 % | 7.7 % | -6.42 % |
| Aligned + HIGH | 14 | +0.94 % | 2.03 | -3.10 % | 7.1 % | -8.91 % |
| Counter + LOW | 16 | +0.94 % | 2.76 | -2.52 % | 0.0 % | -2.72 % |
| Counter + MID | 20 | -1.02 % | 0.54 | -3.63 % | 20.0 % | -24.02 % |
| Counter + HIGH | 20 | -0.54 % | 0.64 | -4.13 % | 10.0 % | -10.53 % |

Counter + HIGH es peor que aligned + HIGH, pero no concentra las pérdidas: 20 %
de la muestra, 15.4 % de pérdidas <-3 % y 25 % de pérdidas <-5 %. Counter + MID,
no HIGH, tiene peor expectancy y contiene el SHORT -24 %. La forma LOW bueno,
MID malo, HIGH menos malo es irregular y no respalda la hipótesis de gradiente.

## 8. ADX rising/falling

Counter + rising: 19 trades, expectancy -0.50 %, PF 0.64, MAE -4.44 % y 15.8 %
de pérdidas <-3 %. Counter + falling: 37, -0.18 %, PF 0.88, MAE -3.01 % y 8.1 %
<-3 %. Combinado parece apoyar la secundaria, pero por lado diverge:

- LONG counter+rising: -1.15 %, PF 0.43, MAE -5.17 %; falling +0.68 %, PF 2.28.
- SHORT counter+rising: +0.23 %, PF 1.33; falling -1.19 %, PF 0.55.

Por tanto, ADX rising podría ser relevante sólo para LONG, pero es un hallazgo
secundario con 10 casos y no justifica otro experimento antes de validar la señal
principal más limpia observada en SHORT.

## 9. LONG

La hipótesis direccional se invierte. Aligned (20) produjo -1.31 % por trade,
PF 0.37 y MAE -3.85 %; counter (30) produjo +0.07 %, PF 1.07 y MAE -3.09 %.
Aligned concentró 20 % de pérdidas <-3 % y <-5 %, frente a 6.7 % y 3.3 % en
counter. Retirar el peor o los dos peores conserva counter mejor en expectancy.
Además, no hay gradiente ADX coherente dentro de counter. No se acepta una señal
LONG basada en la hipótesis principal.

## 10. SHORT

Aquí la dirección DMI sí contiene una asociación interpretable:

- Aligned (24): expectancy +0.72 %, PF 1.73, payoff 2.04, MAE -2.80 %.
- Counter (26): expectancy -0.70 %, PF 0.65, payoff 0.48, MAE -3.96 %.

El contraste temporal conserva dirección: counter menos aligned es -0.26 puntos
en primera mitad y -2.65 en segunda. Tras retirar el SHORT -24 %, sigue en -0.49;
tras retirar los dos peores, -0.12. Al retirar simultáneamente mejor y peor pasa
a +0.05, prácticamente neutral: evidencia moderada, no robusta absoluta.

ADX no ordena el deterioro counter: LOW +1.57 %, MID -2.78 %, HIGH -1.52 %.
Counter + HIGH sólo tiene 5 SHORT, insuficiente para una conclusión fuerte.

## 11. Large losses

Hubo 13 pérdidas <-3 % y 8 <-5 %. Para <-3 %, aligned representa 53.8 % pese a
ser 44 % de trades; counter 46.2 % pese a ser 56 %. Counter+HIGH representa
15.4 % con base 20 %, y counter+rising 23.1 % con base 19 %. Para <-5 %, aligned
y counter aportan 50 % cada uno; counter+HIGH 25 % y counter+rising 12.5 %.

Así, la hipótesis no explica la concentración global de pérdidas grandes. El
archivo `trade_audit.csv` registra cada pérdida con hora, lado, PnL, MFE, MAE,
duración, ADX, DI, alineación, dirección ADX y tercio.

## 12. Large winners

De 14 winners >3 %, 42.9 % fueron aligned y 57.1 % counter, casi idéntico a sus
bases 44/56 %. HIGH produjo 42.9 % con base 34 %, por lo que ADX alto no elimina
movimientos fuertes. De 6 winners >5 %, aligned/counter se reparten 50/50 y los
tres tercios 33/33/33. Cinco de seis tuvieron ADX falling. Un filtro direccional
SHORT podría eliminar ganadores counter importantes: tres de los seis >5 % del
conjunto son counter.

## 13. Outlier robustness

Combinado, counter-aligned pasa de -0.08 puntos a +0.35 al quitar el peor y a
-0.01 al quitar dos: débil. Counter+HIGH mantiene expectancy peor frente al
resto al retirar 0/1/2 extremos, pero no posee gradiente ADX ni concentración de
pérdidas. SHORT counter-aligned conserva signo negativo retirando 0/1/2 peores
(-1.42/-0.49/-0.12), aunque se neutraliza al retirar mejor y peor. LONG mantiene
el signo opuesto. Ninguna conclusión depende exclusivamente del -24 %, pero su
magnitud amplifica SHORT.

## 14. Temporal stability

Combinado, counter-aligned cambia de +1.25 puntos en primera mitad a -1.72 en la
segunda. LONG cambia de +3.57 a -0.81. Sólo SHORT conserva counter peor en ambas
(-0.26 y -2.65), con 9/16 y 17/8 casos counter/aligned respectivamente.

Counter+HIGH cambia de -1.21 a +0.49 combinado y dispone de sólo 2 y 3 SHORT por
mitad; no es estable. Counter+rising es peor combinado en ambas mitades, pero el
desglose SHORT cambia de +0.48 a +0.49 (rising mejor), contrario a la hipótesis.

## 15. Evaluation against criteria

1. Counter peor que aligned: marginal combinado, claro sólo en SHORT.
2. Deterioro creciente con ADX: no cumple.
3. Counter+HIGH concentra pérdidas/MAE: MAE peor, concentración no; muestra SHORT
   demasiado pequeña.
4. Patrón por lado: dirección DMI prometedora en SHORT; inversa en LONG.
5. Outliers: SHORT conserva dirección al retirar hasta dos peores, pero pierde
   fuerza; combinado no es robusto.
6. Mitades: consistente únicamente para alineación SHORT.

## 16. Methodological decision

**Conclusión C: hipótesis general rechazada, pero señal específica SHORT aceptada
para investigación.** La parte aceptada es alineación direccional DMI, no fuerza
ADX alta. No se crea filtro.

Único siguiente experimento propuesto: pre-registrar una variante que permita
entradas SHORT sólo cuando `-DI > +DI`, mantenga todas las salidas intactas y se
evalúe primero en un snapshot futuro no solapado. No debe incluir ADX, ATR ni
otros filtros. Deberá exigir mejora de expectancy/PF/MAE, conservar una fracción
predefinida de trades y ganancias grandes, y replicar el signo en subperiodos.
No se implementa en esta tarea.

## 17. Reproducibility

```bash
.venv/bin/python -m research.adx_trend_analysis
```

Artefactos: `trade_audit.csv`, `grouped_metrics.csv`,
`event_concentration.csv`, `outlier_robustness.csv`, `temporal_stability.csv` y
`summary.json` bajo `research/output/adx_trend_analysis/`. El código está en
`research/adx_trend_analysis.py` y sus tests en
`tests/test_adx_trend_analysis.py`.
