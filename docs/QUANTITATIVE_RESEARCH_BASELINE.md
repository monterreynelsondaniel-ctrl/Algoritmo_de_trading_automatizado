# Investigación cuantitativa de la estrategia baseline

Fecha del análisis: 2026-09-03. Snapshot inmutable:
`data/snapshots/btcusdt_4h_2026_08.csv` (2,199 velas 4h, desde
2025-08-27 12:00 UTC hasta 2026-08-28 20:00 UTC).

Este informe es diagnóstico. No modifica entradas, salidas ni parámetros de la
estrategia. Las variables de señal usan Heikin-Ashi; ejecución, contexto de
precio y recorridos usan OHLC real. Las variables candidatas sólo usan datos
disponibles al cierre de la vela de señal. MFE, MAE, duración y trayectoria son
resultados posteriores y no pueden usarse en vivo en su forma final.

## A. Baseline confirmada

Se reprodujeron 100 operaciones cerradas y una SHORT abierta, excluida de las
estadísticas. Costes vigentes: comisión taker 0.04 % por lado, slippage 0.05 %
por ejecución y funding fijo estimado 0.01 % por cada ciclo completo de 8h.

| Métrica | Sin fricción (baseline conocida) | Baseline neta actual |
|---|---:|---:|
| Trades / wins / losses | 100 / 55 / 45 | 100 / 51 / 49 |
| Win rate | 55.00 % | 51.00 % |
| Suma P&L | +3.36 % | -25.10 % |
| Retorno compuesto | -6.72 % | -30.02 % |
| Profit factor | 1.03 | 0.83 |
| Mejor / peor | +13.38 / -23.55 % | +13.12 / -24.02 % |
| MFE / MAE medio | +3.10 / -3.35 % | +3.05 / -3.40 % |
| Duración media / mediana | 85.96h / n.d. | 85.96h / 68h |

La diferencia no es una alteración de señales: +3.36 % bruto coincide. Proviene
de 18.48 puntos de comisiones más funding y 9.98 puntos de slippage estimado.
El funding del snapshot no es histórico observado, por lo que esa porción debe
interpretarse como supuesto, no como medición.

## B. Hallazgos principales

1. El edge bruto es demasiado estrecho para las fricciones actuales. PF bruto
   1.025 se convierte en 0.830 neto.
2. La cola izquierda domina: skewness -1.73. Q5=-7.05 %, mediana=+0.06 % y
   Q95=+5.21 %. Las pérdidas medias (-3.02 %) superan las ganancias medias
   (+2.41 %); payoff 0.80.
3. Las 13 pérdidas inferiores a -3 % suman -105.83 %. Diez de ellas nunca
   alcanzaron MFE de +1 %: predominan entradas que no funcionaron, no beneficios
   grandes desperdiciados.
4. El comportamiento comienza a separarse pronto: a 12h winners promedian
   +0.50 % y losers -0.84 %; a 24h, +1.04 % frente a -1.26 %; a 48h,
   +2.10 % frente a -2.03 %. Es descriptivo y condicionado por el resultado.
5. La expansión de ATR al entrar es la característica preentrada con mayor
   separación y dirección estable entre mitades: winners 0.940 versus losers
   1.029 veces su media ATR de 20 barras. Sigue sin demostrar causalidad.
6. Magnitud absoluta, pendiente y retracement de SQZMOM separan poco y de modo
   inestable. No hay evidencia para un umbral de SQZMOM común.

## C. LONG

| Métrica | Valor |
|---|---:|
| Trades / win rate | 50 / 50.00 % |
| Expectancy / suma neta | -0.484 % / -24.18 % |
| Suma bruta | -10.13 % |
| Profit factor | 0.667 |
| Media / mediana | -0.484 % / -0.091 % |
| Desv. estándar / skewness | 3.76 / -1.86 |
| Mejor / peor | +6.64 % / -15.61 % |
| Ganancia / pérdida media | +1.93 % / -2.90 % |
| Payoff | 0.667 |
| MFE / MAE medio | +2.60 % / -3.39 % |
| Duración media / mediana | 83.36h / 66h |

LONG falla tanto antes como después de costes: el P&L bruto ya era -10.13 %.
Sólo 4 LONG fueron clasificados a favor de la tendencia simple y sumaron
+7.73 % (media +1.93 %); los otros 46 sumaron -31.91 %. La muestra favorable es
demasiado pequeña para adoptar un filtro. Los LONG winners tuvieron expansión
ATR 0.948 frente a 1.053 en losers, diferencia consistente entre mitades. Los
descriptores SQZMOM fueron débiles; winners incluso tuvieron un reversal medio
menos profundo (4.5 % del extremo) que losers (8.5 %), contrario a la idea
simple de que más retracement siempre es mejor.

## D. SHORT

| Métrica | Valor |
|---|---:|
| Trades / win rate | 50 / 52.00 % |
| Expectancy / suma neta | -0.018 % / -0.92 % |
| Suma bruta | +13.49 % |
| Profit factor | 0.988 |
| Media / mediana | -0.018 % / +0.074 % |
| Desv. estándar / skewness | 5.10 / -1.71 |
| Mejor / peor | +13.12 % / -24.02 % |
| Ganancia / pérdida media | +2.87 % / -3.14 % |
| Payoff | 0.912 |
| MFE / MAE medio | +3.51 % / -3.40 % |
| Duración media / mediana | 88.56h / 74h |

SHORT parece mejor porque captura casi todos los movimientos grandes: 10 de 14
ganadoras superiores a +3 % y las dos superiores a +10 %. Su ganancia media es
48 % mayor que LONG. No obstante, una sola pérdida (-24.02 %) consume 16.2 % de
todas las pérdidas y elimina el edge neto. SHORT bajo squeeze ON sumó +25.67 %
(18 trades, media +1.43 %) y bajo squeeze OFF -26.58 % (32, media -0.83 %).
Es una interacción prometedora pero exploratoria y sensible al outlier.

## E. Pérdidas extremas

| Grupo | N (L/S) | Suma | MFE medio | MAE medio | Duración media |
|---|---:|---:|---:|---:|---:|
| PnL < -3 % | 13 (6/7) | -105.83 % | +0.57 % | -11.77 % | 164h |
| PnL < -5 % | 8 (5/3) | -86.07 % | +0.74 % | -15.61 % | 193h |
| PnL < -10 % | 3 (2/1) | -50.15 % | +0.64 % | -23.95 % | 225h |

La pérdida #99 fue SHORT desde 2026-08-19 04:00 UTC: entrada real 64,296.3,
salida 79,440.1, -23.55 % bruto y -24.02 % neto en 200h. El reversal fue casi
marginal: SQZMOM cayó apenas 0.53 % desde su máximo reciente después de 26 barras
de impulso; precio sobre SMA20/SMA50, régimen UP, squeeze OFF y ATR expandiéndose
(1.159). Ya iba -6.63 % a 12h, -7.65 % a 24h y -15.90 % a 48h, con MFE total
sólo +0.21 %. Esto apunta a invalidación temprana/stop, no profit protection.

Los tres desastres <-10 % estaban en squeeze OFF y duraron en promedio 225h.
En las 13 pérdidas <-3 %, ocho eran squeeze OFF. No hay una única condición de
entrada común suficiente: aparecen en los tres regímenes. Sí comparten poca
excursión favorable y duración prolongada. Reducir exposición requeriría sizing
por riesgo/ATR; evitar o cerrar necesitaría validar por separado contracción de
ATR, contexto direccional y confirmación temprana, sin inferir umbral óptimo aquí.

## F. MFE/MAE y salida

Winners: MFE +4.61 %, MAE -1.45 %, PnL +2.41 % y giveback MFE-a-neto 2.21
puntos. Losers: MFE +1.43 %, MAE -5.42 %, PnL -3.02 % y giveback 4.45 puntos.

- 29 losers alcanzaron MFE >=1 %, pero sólo 5 alcanzaron >=3 % y ninguno >=5 %.
- Esos cinco casos MFE>=3 % terminaron sumando -5.67 %: justifican estudiar
  protección de beneficios, aunque no explican la cola destructiva.
- 10 de las 13 pérdidas <-3 % tuvieron MFE <1 %: candidatas a invalidación/stop.
- Cuatro winners soportaron MAE <-3 %: un stop estrecho podría destruir trades
  válidos y debe evaluarse con recorrido intrabar y orden de eventos más preciso.

Prioridad de salidas: (1) límite de riesgo/invalidación, (2) time stop o revisión
obligatoria de trades estancados, (3) protección de MFE sólo para el subconjunto
que primero logra avance suficiente. Breakeven, trailing y parciales no tienen
aún evidencia para escoger distancias concretas.

## G. SQZMOM y calidad del reversal

Las comparaciones normalizan SQZMOM por precio. Winners y losers tuvieron
magnitud absoluta 2.33 % y 2.26 %, amplitud previa 4.87 % y 4.63 %, y 13.8 y
15.3 barras de impulso. Las diferencias son pequeñas. En LONG, winners mostraron
menor delta de reversal (0.064 % vs 0.088 %) y retracement (0.045 vs 0.085). En
SHORT, delta fue prácticamente idéntico (-0.067 % vs -0.066 %) y winners tuvieron
retracement algo mayor (0.102 vs 0.076), sin estabilidad temporal.

Conclusión: signo y cambio de color definen la señal, pero valor absoluto,
pendiente, aceleración, distancia a cero, extremo reciente, duración/amplitud del
impulso no muestran por sí solos potencial predictivo robusto. El caso #99
respalda investigar reversals marginales sólo como interacción con tendencia y
expansión de volatilidad; no autoriza un cutoff.

## H. Contexto de mercado

- Régimen simple: RANGE +14.32 % (50 trades), DOWN -2.80 % (26), UP -36.62 %
  (24). UP está dominado parcialmente por el SHORT extremo.
- A favor de tendencia: sólo 9 observaciones. LONG 4 sumaron +7.73 %; SHORT 5
  sumaron +4.92 %. Interesante, muestra insuficiente.
- Volatilidad por mediana ATR: mitad alta +10.17 %, PF 1.15; mitad baja -35.27 %,
  PF 0.56. El peor outlier estaba en volatilidad baja, por lo que no equivale a
  afirmar que alta volatilidad siempre ayuda.
- Squeeze ON: 33 trades, +16.12 %, PF 1.43. OFF: 67, -41.22 %, PF 0.63. El efecto
  se concentra en SHORT; LONG fue negativo en ambos estados. No hubo señales en
  estado `no squeeze` en esta muestra.

## I. Duración, trayectoria, temporalidad y fragilidad

| Duración | N | Win rate | Suma neta | PF |
|---|---:|---:|---:|---:|
| <24h | 2 | 50.0 % | -2.85 % | 0.02 |
| 24-48h | 11 | 27.3 % | -9.34 % | 0.13 |
| 48-72h | 41 | 68.3 % | +55.50 % | 4.79 |
| 3-5 días | 24 | 54.2 % | +30.23 % | 2.99 |
| >5 días | 22 | 27.3 % | -98.64 % | 0.06 |

La relación duración/resultado es fuerte pero endógena: el trade dura hasta la
señal opuesta. No prueba que cerrar al quinto día produzca esos resultados.

Sólo 4 de 12 meses fueron positivos. Febrero y junio aportaron +31.59 puntos;
noviembre y agosto restaron -39.11. Ningún comportamiento es estable mes a mes.
El mejor trade representa 10.7 % de ganancias; los mejores 5, 34.1 %. El peor
representa 16.2 % de pérdidas; los peores 5, 45.6 %.

Sensibilidad: quitar el mejor deja -38.22 %; quitar el peor deja -1.08 %; quitar
los 3 peores da +25.05 %, mientras quitar los 3 mejores da -55.61 %. La estrategia
es frágil a ambas colas, especialmente a la izquierda.

## J. Ranking de hipótesis

### Alta prioridad

1. **Contracción/expansión de ATR al reversal (ambos, especialmente LONG).** Es
   el mayor efecto preentrada, estable en ambas mitades: winners 0.940, losers
   1.029. Riesgo medio-alto de overfitting por selección entre muchas variables.
   Probar una sola regla semántica pre-registrada en datos fuera de muestra.
2. **Invalidación/límite de riesgo para trades sin avance.** Diez de trece grandes
   pérdidas tuvieron MFE <1 %, y winners/losers ya divergen a 12–24h. Aplica a
   ambos. Alto riesgo de sesgo si se eligen hora y umbral mirando esta muestra;
   comparar pocas reglas previamente justificadas y usar OHLC intrabar.
3. **Reglas LONG/SHORT separadas.** LONG no tiene edge bruto; SHORT sí, pero es
   vulnerable a rallies. Riesgo bajo como estructura experimental; no implica
   apagar LONG sin validación.

### Prioridad media

1. **Squeeze ON específico de SHORT.** +25.67 % frente a -26.58 % OFF. Riesgo
   alto por interacción pequeña y outlier; exigir estabilidad fuera de muestra.
2. **Alineación con tendencia.** Nueve casos a favor sumaron +12.65 %. Riesgo muy
   alto por N pequeño; validar la definición fija SMA20/SMA50 sin buscar ventanas.
3. **Time stop.** >5 días concentra -98.64 %. Es posterior/endógeno; simular una
   regla fija sólo después de resolver el orden intrabar y validar fuera de muestra.
4. **Protección de MFE.** Cinco losers dieron >3 % de MFE. Puede recuperar una
   fracción, no resolver la mayoría de pérdidas extremas.

### Prioridad baja

- Tamaño de vela, volatilidad realizada y posición en rango: efectos modestos o
  inconsistentes entre lados/mitades.
- Barras y amplitud del impulso previo: diferencias pequeñas; podrían servir en
  interacción, no como filtro independiente.

### Sin evidencia

- Umbral común de magnitud absoluta de SQZMOM.
- Pendiente/aceleración o profundidad del reversal como señal aislada.
- Un mismo filtro simétrico para LONG y SHORT.
- Parciales, trailing o breakeven con distancias específicas: no se derivan de
  estos datos sin optimización adicional.

## K. Próximo experimento recomendado: uno solo

**Hipótesis:** entrar durante expansión inmediata de ATR degrada la calidad del
reversal; exigir que ATR(14) real no esté por encima de su media de 20 barras
debería reducir pérdidas sin eliminar la mayor parte de la cola positiva.

La variable será `atr_expansion = ATR(14) / mean(ATR(14), 20)`, calculada al
cierre de señal sin lookahead. Se pre-registra un único corte natural `<=1.0`;
no se barrerán longitudes ni thresholds. La baseline actual queda intacta.

Prueba: congelar este dataset como desarrollo, obtener después un período no
solapado y evaluar primero combinado y luego LONG/SHORT sólo como desglose.
Aceptar para una segunda réplica si, fuera de muestra, mejora expectancy y PF
netos frente a baseline, reduce pérdida media y conserva al menos 70 % de trades
y 70 % de la suma de ganancias positivas. Rechazar si falla cualquiera de los
criterios principales (expectancy/PF) o si el signo del efecto se invierte. Aun
si acepta, requerirá otra réplica temporal antes de convertirse en decisión.

## L. Reproducibilidad, archivos y tests

Comando:

```bash
.venv/bin/python -m research.strategy_diagnostics \
  --snapshot btcusdt_4h_2026_08
```

Archivos creados: `research/__init__.py`, `research/strategy_diagnostics.py`,
`tests/test_strategy_diagnostics.py`, este informe y los CSV/JSON bajo
`research/output/btcusdt_4h_2026_08/`. Se actualizaron únicamente documentos de
contexto y próximos pasos. No se modificó snapshot, engine, indicadores, señales
ni reglas de ejecución.

Los artefactos contienen los 100 trades enriquecidos, comparaciones de features,
trayectorias censuradas a la duración real, grupos extremos, regímenes, meses y
pruebas de fragilidad. Toda asociación es exploratoria: se inspeccionaron muchas
variables sobre una única muestra, no se corrigió formalmente por selección
múltiple y no existe todavía evidencia predictiva fuera de muestra.
