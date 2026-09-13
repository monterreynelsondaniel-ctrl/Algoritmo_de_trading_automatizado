# Strategy 2 — auditoría comparativa ENTRY V1 ↔ V2

Fecha: 2026-09-13. Clasificación: descriptiva, experimental y estrictamente
pre-outcome. No se cargaron resultados posteriores ni se hicieron llamadas
OpenAI durante esta auditoría.

## 1. Identidad

La comparación une uno a uno los mismos 81 candidates del bundle
`btcusdt_1d_4h_1h_2026_08`:

| Contrato | Run live | Prompt | Schema | Modelo |
|---|---|---|---|---|
| V1 | `7c6f4b7f-b7fd-457a-8d43-b6b289d94558` | `strategy2-entry-v1` | `1.0.0` | Terra low |
| V2 | `f0432b91-9104-4c8c-8e74-0064fa354a41` | `strategy2-entry-v2` | `1.1.0` | Terra low |

```text
Candidate sequence: 437f242e6f96d8c441359321d10c48e317f8281cb5be86a39501843db808285a
V1 input sequence:  6115bd906cf50d587e72310ac0985e186d59381c6ac15c87464ed1902c282ccd
V2 input sequence:  521c0adecf70ffcbdfbde21dda75abb93d09802fa9f5da28d4147c5cb8bd67c2
```

## 2. Cambio de decisiones

| Métrica | V1 | V2 |
|---|---:|---:|
| Candidates | 81 | 81 |
| LONG | 18 | 18 |
| SHORT | 63 | 63 |
| APPROVE | 8 | 33 |
| REJECT | 73 | 48 |
| Approval rate | 9.88 % | 40.74 % |
| LONG APPROVE | 0 | 7 |
| SHORT APPROVE | 8 | 26 |

Transiciones:

```text
APPROVE V1 -> APPROVE V2:  8
APPROVE V1 -> REJECT V2:   0
REJECT V1  -> APPROVE V2: 25 (7 LONG / 18 SHORT)
REJECT V1  -> REJECT V2:  48
```

V2 no perdió ninguno de los approvals V1.

## 3. Los 25 nuevos APPROVE

En V1 estos candidates se rechazaban principalmente mediante códigos dispersos
de conflicto multi-timeframe, tendencia débil y lectura del signo SQZMOM como
dirección absoluta. En V2 aparecen de forma consistente:

| Reason code V2 | Casos / 25 |
|---|---:|
| `TREND_ALIGNED` | 25 |
| `SETUP_CONFIRMED` | 25 |
| `CONFIRMATION_STRONG` | 25 |
| `MOMENTUM_REVERSAL_CLEAR` | 24 |
| `DMI_ALIGNED` | 21 |
| `EMA_ALIGNED` | 19 |
| `ADX_STRONG` | 17 |

V2 parece distinguir mejor el reversal determinista de la mera señal algebraica
del histograma. Aun así, algunos approvals conservan conflictos locales: seis
incluyen `EMA_CONFLICT`, cinco `DMI_CONFLICT` y cinco `ADX_WEAK`. El reviewer
parece considerar que la alineación estratégica global puede coexistir con una
debilidad puntual; esto no es todavía evidencia de calidad trading.

## 4. Los siete LONG aprobados

Los siete eran REJECT en V1. Cuatro de ellos habían recibido códigos que trataban
SQZMOM negativo 1H/4H como evidencia bajista. V2 reconoce en los siete:

```text
TREND_ALIGNED:             7/7
SETUP_CONFIRMED:           7/7
CONFIRMATION_STRONG:       7/7
MOMENTUM_REVERSAL_CLEAR:   7/7
DMI_ALIGNED:               6/7
EMA_ALIGNED:               5/7
ADX_STRONG:                3/7
```

Esto es coherente con la corrección pre-outcome: `dark_red -> light_red` sigue
bajo cero, pero representa recuperación del momentum negativo hacia cero. No se
puede afirmar todavía que estos LONG sean correctos o rentables.

## 5. Los ocho approvals V1

Los ocho sobrevivieron como APPROVE. En V1 sus explicaciones estaban dominadas
por tendencia bajista, `-DI`, precio bajo EMAs y fuerza ADX. V2 conserva esa base:

```text
TREND_ALIGNED:             8/8
SETUP_CONFIRMED:           8/8
CONFIRMATION_STRONG:       8/8
DMI_ALIGNED:               8/8
EMA_ALIGNED:               8/8
MOMENTUM_REVERSAL_CLEAR:   8/8
ADX_STRONG:                7/8
```

La permanencia no depende de un cambio de candidates, modelo o reasoning.

## 6. Estabilidad de reason codes

| Métrica | V1 | V2 |
|---|---:|---:|
| Códigos únicos | 209 | 14 |
| Códigos singleton | 167 | 0 |
| Códigos fuera del enum | N/A | 0 |

La taxonomía V2 es mucho más agregable. Sin embargo, se detectaron tres
asignaciones con pares opuestos dentro de la misma respuesta:

- candidate 69: `TREND_ALIGNED` y `TREND_CONFLICT` (REJECT);
- candidate 35: `DMI_ALIGNED` y `DMI_CONFLICT` (APPROVE);
- candidate 77: `ADX_STRONG` y `ADX_WEAK` (APPROVE).

Pueden referirse a temporalidades distintas, pero los códigos no codifican el
timeframe. La estabilidad léxica mejoró; la precisión semántica aún tiene esta
limitación y no debe ocultarse.

## 7. Equilibrio LONG/SHORT

```text
LONG approval rate:  38.89 % (7/18)
SHORT approval rate: 41.27 % (26/63)
Diferencia absoluta: 2.38 puntos porcentuales
```

V2 es descriptivamente equilibrado por lado. Las razones predominantes son las
mismas familias controladas y coherentes con cada candidate. Esto corrige la
asimetría extrema 0/18 de V1, pero no demuestra que el equilibrio sea deseable.

## 8. Replay y seguridad

El replay V2 completó:

```text
81 cache hits
0 live calls
33 APPROVE / 48 REJECT
positions = 0
trades = 0
EXIT reviews = 0
cost = $0
```

El backup post-V2 es
`database/backups/ai_decisions_post_v2_20260913_084349.db`. Su SHA-256 coincide
con la DB al momento del backup:

```text
7cabbb5174be7eafec1c075b4c1f1f4e0b4a22d03b69a055734d0990e85f203b
```

Ambos archivos permanecen ignorados por Git.

## 9. Limitación explícita

> Esta auditoría no utiliza PnL, win/loss, MFE, MAE, retornos, exits ni velas posteriores al evaluation time.

Los cambios observados describen cómo Terra respondió al contrato semántico V2.
No establecen que V2 tenga edge ni que sea superior como filtro de trading.
