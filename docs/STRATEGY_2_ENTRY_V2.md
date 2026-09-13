# Strategy 2 — experimento ENTRY REVIEW V2

Fecha: 2026-09-13. Estado: contrato y collection live completados; outcomes aún cerrados.

## Motivo pre-outcome

La auditoría V1 mostró una ambigüedad semántica: el reviewer recibía el valor
SQZMOM actual, pero no los colores anterior/actual ni el significado del
reversal que Strategy 2 ya había detectado. En particular, un LONG permanece
bajo cero durante `dark_red -> light_red`; el signo negativo podía interpretarse
como continuación bajista aunque el histograma estuviera recuperándose.

V2 corrige únicamente esa representación. No se consultaron PnL, outcomes,
MFE/MAE ni velas posteriores, y no se cambiaron candidatos, indicadores,
thresholds, modelo o reasoning.

## Contratos congelados

| Contrato | Prompt | Schema | Payload |
|---|---|---|---|
| V1 | `strategy2-entry-v1` | `1.0.0` | Numérico histórico |
| V2 | `strategy2-entry-v2` | `1.1.0` | V1 + semántica causal del reversal |

V1 sigue siendo el default para preservar compatibilidad. V2 se selecciona
explícitamente con `--entry-review-version v2`.

## Payload semántico V2

V2 añade:

- `candidate_side`, `setup_direction` y `confirmation_direction`;
- para setup 4H y confirmación 1H: valor y color SQZMOM anterior/actual,
  transición, interpretación y significado dentro de Strategy 2.

La información se toma de las mismas dos velas cerradas que activaron las reglas
deterministas. No se añade ningún indicador ni dato posterior.

## Reason codes controlados

```text
TREND_ALIGNED / TREND_CONFLICT
SETUP_CONFIRMED / SETUP_WEAK
CONFIRMATION_STRONG / CONFIRMATION_WEAK
DMI_ALIGNED / DMI_CONFLICT
ADX_STRONG / ADX_WEAK
EMA_ALIGNED / EMA_CONFLICT
MOMENTUM_REVERSAL_CLEAR / MOMENTUM_REVERSAL_WEAK
```

El schema rechaza cualquier código libre. Confidence se conserva como metadata;
no determina la decisión ni se utiliza como filtro.

## Identidad reproducible

```text
Bundle hash:
a3176515d0c61ddb9ea210dca710f014957ee1ef80d813b75826da3d1977b840

Candidate sequence (V1 = V2):
437f242e6f96d8c441359321d10c48e317f8281cb5be86a39501843db808285a

V1 AI input sequence:
6115bd906cf50d587e72310ac0985e186d59381c6ac15c87464ed1902c282ccd

V2 AI input sequence:
521c0adecf70ffcbdfbde21dda75abb93d09802fa9f5da28d4147c5cb8bd67c2
```

Prompt, schema, payload e input hash separan las caches V1/V2. Las 81 decisiones
V1 no son hits legítimos para V2.

## Preflight V2

```bash
.venv/bin/python -m backtest.strategy_2_run \
  --bundle btcusdt_1d_4h_1h_2026_08 \
  --ai-preflight \
  --entry-review-version v2
```

Resultado validado: 81 candidates (18 LONG/63 SHORT), 0 cache hits V2 y 81
misses live. El coste esperado ENTRY es aproximadamente `$0.455`. La reserva
conservadora usando el máximo de 2,000 output tokens por llamada es `$2.514`,
ligeramente superior al límite local `$2.50`; esto debe resolverse explícitamente
antes de autorizar live. No se cambió el presupuesto ni se hicieron llamadas.

## Estado posterior del collector

La collection autorizada produjo 33 APPROVE y 48 REJECT. Un replay posterior
confirmó las 81 decisiones desde cache con cero llamadas y cero coste. La
comparación V1/V2 está documentada en `STRATEGY_2_ENTRY_V2_AUDIT.md`.

## Limitación

V2 no está demostrado como mejor que V1. Sólo elimina una ambigüedad de input
detectada sin outcomes. Cualquier comparación de decisiones debe permanecer
pre-outcome hasta que ambas colecciones estén congeladas.
