# Strategy 2 — auditoría descriptiva pre-outcome de ENTRY REVIEW

Fecha: 2026-09-11. Clasificación: descriptiva, exploratoria y estrictamente
pre-outcome. No se realizaron llamadas OpenAI durante esta auditoría.

## A. Dataset

Se auditó el run live `7c6f4b7f-b7fd-457a-8d43-b6b289d94558`, completado con
`gpt-5.6-terra`, reasoning `low`, prompt `strategy2-entry-v1`, schema `1.0.0`,
Strategy `strategy_2_v1` y bundle `btcusdt_1d_4h_1h_2026_08`.

```text
Candidates: 81 (18 LONG / 63 SHORT)
APPROVE:     8
REJECT:     73
```

```text
Candidate sequence:
437f242e6f96d8c441359321d10c48e317f8281cb5be86a39501843db808285a

AI input sequence:
6115bd906cf50d587e72310ac0985e186d59381c6ac15c87464ed1902c282ccd
```

La cache contiene 81 keys/candidate IDs únicos. Las 81 respuestas pasan el
schema y coinciden con el side solicitado.

## B. Approval behavior

| Grupo | N | APPROVE | REJECT | Approval rate |
|---|---:|---:|---:|---:|
| Total | 81 | 8 | 73 | 9.88 % |
| LONG | 18 | 0 | 18 | 0.00 % |
| SHORT | 63 | 8 | 55 | 12.70 % |

No puede inferirse calidad predictiva ni rentabilidad de estas tasas.

## C. APPROVE profile

Los ocho aprobados fueron SHORT y mostraron una agrupación descriptiva fuerte:

- 8/8 tenían DMI alineado con SHORT en 1D, 4H y 1H.
- 8/8 tenían `close` bajo EMA10 y EMA55 en 1D y 4H; 6/8 también en 1H.
- La dirección EMA era bajista en 8/8 en 1D, 7/8 en 4H y 8/8 en 1H.
- ADX medio: 33.77 en 1D, 31.44 en 4H y 34.00 en 1H, frente a 27.04,
  25.14 y 26.32 en REJECT.
- El spread `+DI - -DI` medio fue fuertemente bajista: -19.05, -11.86 y
  -12.84 en 1D/4H/1H. En REJECT fue -1.45, +2.83 y +0.88.
- El tiempo setup-confirmation medio fue 39.38 h frente a 26.51 h en REJECT.
  Esto es descriptivo; no autoriza un tiempo mínimo.

| # | Evaluation UTC | Conf. | ADX 1D/4H/1H | DMI 1D/4H/1H | SQZMOM 4H/1H | Razones principales |
|---:|---|---:|---|---|---|---|
| 16 | 2025-11-09 11:00 | .82 | 28.84/31.64/22.47 | bearish/bearish/bearish | 344/54 | daily/4H bearish, 1H -DI, ADX support |
| 17 | 2025-11-12 16:00 | .86 | 29.23/16.98/28.90 | bearish/bearish/bearish | -800/1223 | DI+EMA alignment, price below EMAs |
| 36 | 2026-01-31 03:00 | .82 | 26.15/37.00/41.34 | bearish/bearish/bearish | -3888/1506 | daily/4H bearish, 1H -DI, ADX strength |
| 42 | 2026-03-07 19:00 | .87 | 38.59/20.73/49.24 | bearish/bearish/bearish | -3234/11 | bearish DMI/EMA across timeframes |
| 61 | 2026-06-03 16:00 | .94 | 31.00/58.69/59.60 | bearish/bearish/bearish | -4415/381 | multi-TF bearish, strong ADX, below EMAs |
| 62 | 2026-06-10 22:00 | .84 | 45.11/31.29/19.71 | bearish/bearish/bearish | -727/406 | bearish confirmation and -DI alignment |
| 67 | 2026-06-24 10:00 | .84 | 34.63/18.44/23.49 | bearish/bearish/bearish | -1254/426 | bearish EMA and directional alignment |
| 68 | 2026-06-29 14:00 | .91 | 36.64/36.74/27.29 | bearish/bearish/bearish | 280/445 | below EMAs, -DI dominant, ADX strength |

Los aprobados no forman un cluster uniforme por signo SQZMOM 4H: seis eran
negativos y dos positivos. Los ocho tenían SQZMOM 1H positivo, como también los
55 SHORT rechazados; el signo 1H por sí solo no separa decisiones SHORT.

## D. REJECT profile

Los rechazos muestran principalmente falta de confirmación multi-timeframe:

- Sólo 22/73 tenían DMI alineado con el candidate en 4H y 28/73 en 1H.
- 38/73 contenían algún reason code con `CONFLICT`.
- 35/73 contenían `WEAK` o `LOW`.
- 43/73 mencionaban `MOMENTUM` o `SQZMOM`.
- `MULTI_TIMEFRAME_CONFLICT` fue el código exacto más frecuente: 13 casos.

Las agrupaciones anteriores son búsquedas lexicales transparentes sobre códigos
libres, no categorías definidas por el schema.

## E. LONG analysis

Los 18 LONG fueron rechazados. Los códigos exactos más repetidos fueron:

| Reason code | Count |
|---|---:|
| `NEGATIVE_MOMENTUM` | 4 |
| `MULTI_TIMEFRAME_CONFLICT` | 3 |
| `CONFIRMATION_1H_BEARISH_TREND` | 3 |
| `CONFIRMATION_1H_NEGATIVE_MOMENTUM` | 2 |
| `SETUP_4H_NEGATIVE_MOMENTUM` | 2 |
| `BEARISH_4H_TREND` | 2 |
| `LONG_COUNTERTREND` | 2 |

Aunque 14/18 tenían DMI diario alineado con LONG, sólo 6/18 mantenían esa
alineación DMI en 4H y 8/18 en 1H. La dirección EMA se alineaba con LONG en
17/18 en 1D, pero sólo 9/18 en 4H y 5/18 en 1H.

Existe además una limitación crítica del input: los 18 LONG tenían SQZMOM 1H
negativo porque la confirmación LONG ocurre dentro del lado rojo del histograma.
Terra recibió sólo el valor actual; no recibió color actual/anterior, cambio ni
pendiente. Por ello no podía distinguir directamente “momento negativo que se
revierte” de “momento negativo que continúa”, y varios summaries/códigos lo
describieron simplemente como señal bajista. Esto puede explicar parte de la
asimetría, pero no demuestra por sí solo un bias del modelo.

## F. SHORT analysis

Comparados con los 55 SHORT rechazados, los ocho aprobados presentaron:

| Feature media | SHORT APPROVE | SHORT REJECT |
|---|---:|---:|
| ADX 1D | 33.77 | 27.14 |
| ADX 4H | 31.44 | 24.57 |
| ADX 1H | 34.00 | 25.47 |
| DMI spread 1D | -19.05 | -4.46 |
| DMI spread 4H | -11.86 | +6.50 |
| DMI spread 1H | -12.84 | +3.24 |
| Close vs EMA55 1D | -9.92 % | -4.83 % |
| Close vs EMA55 4H | -3.38 % | +0.75 % |
| Close vs EMA55 1H | -1.48 % | +0.34 % |

La separación más consistente es la alineación direccional bajista simultánea,
no una variable aislada. Con sólo ocho observaciones no debe convertirse en
threshold ni filtro.

## G. Reason codes

Los 81 resultados contienen 284 asignaciones y 209 códigos distintos; 167
aparecen una sola vez. El vocabulario es muy fragmentado porque `reason_codes`
acepta strings libres.

APPROVE se expresó mediante variantes de:

- tendencia bajista diaria/4H;
- `-DI` dominante;
- precio bajo EMAs;
- fuerza ADX multi-timeframe.

REJECT se expresó principalmente mediante:

- conflicto entre timeframes;
- tendencia débil/ADX bajo;
- DMI contrario al side;
- signo de momentum interpretado como contrario.

No se detectaron códigos lexicalmente contradictorios en APPROVE ni summaries
que dijeran explícitamente lo contrario de la decisión.

## H. Confidence

| Grupo | Mean | Median | P25 | P75 | Min | Max |
|---|---:|---:|---:|---:|---:|---:|
| APPROVE | .863 | .850 | .835 | .880 | .82 | .94 |
| REJECT | .855 | .860 | .780 | .930 | .70 | .99 |
| LONG | .879 | .900 | .820 | .945 | .74 | .99 |
| SHORT | .849 | .860 | .780 | .910 | .70 | .98 |

Confidence no discrimina APPROVE/REJECT: sus medias y medianas son casi iguales,
y 28 de 73 rechazos tienen confidence mayor o igual a .90. No hay evidencia
para usar confidence como threshold.

## I. Schema consistency

No se encontraron:

- campos faltantes o nulos inesperados;
- enums inválidos;
- side mismatches;
- candidate IDs o input hashes duplicados;
- summaries lexicalmente opuestos a la decisión;
- requests sin cache correspondiente.

`setup_quality`, `market_location`, `technical_space` y `risk_flags` no existen
en el schema real. Tampoco se enviaron colores SQZMOM, cambio ni pendiente; no
se inventaron esos campos durante la auditoría.

## J. Temporal distribution

Los APPROVE se concentraron en cuatro meses:

```text
2025-11: 2
2026-01: 1
2026-03: 1
2026-06: 4
```

Junio contiene 50 % de las aprobaciones, pero sólo ocho candidates ese mes.
Todos los demás meses tuvieron cero APPROVE. Esto describe permisividad temporal;
sin outcomes no permite afirmar que junio fuera un mejor régimen de trading.

## K. Hypotheses

Observaciones que podrían contrastarse después, sin adoptarlas como reglas:

1. Terra parece exigir alineación bajista simultánea de DMI/EMA en 1D, 4H y 1H
   para aprobar SHORT.
2. La ausencia de dinámica/color SQZMOM puede hacer que Terra confunda la
   semántica reversal con la dirección absoluta del histograma, especialmente
   en LONG.
3. Confidence representa seguridad de la clasificación emitida, no proximidad
   a APPROVE; probablemente no sea una variable de ranking útil.
4. El vocabulario libre de reason codes dificulta agregación estable; una futura
   versión podría estudiar taxonomía cerrada, pero cambiarla sería otro prompt/schema.
5. La concentración temporal de APPROVE puede corresponder a la prevalencia de
   alineación bajista fuerte, no a una preferencia temporal del modelo.

Ninguna hipótesis fue contrastada con resultados posteriores en esta tarea.

## L. Explicit limitation

> Esta auditoría no utiliza ningún outcome futuro y no evalúa todavía si las decisiones AI fueron rentables.

Todas las features principales proceden literalmente del payload ENTRY. Las
relaciones EMA, spread/dirección DMI y timing son transformaciones causales de
esos mismos valores; no se incorporaron velas ni indicadores adicionales.
