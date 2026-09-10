# Strategy 2 — ENTRY decision collection

Fecha: 2026-09-10. Estado: implementado y validado únicamente en replay/offline.
No se realizaron llamadas OpenAI.

## Tres modos distintos

```text
--ai-preflight
  estima candidates, tokens y coste; no solicita decisiones

--ai-entry-collect
  revisa todos los ENTRY candidates independientes; siempre permanece flat

sin ambos flags
  full backtest path-dependent; puede abrir y gestionar posiciones simuladas
```

## Semántica del collector

El collector reutiliza `enumerate_flat_entry_candidates()` y el mismo
`build_entry_request()` consumido por el full backtest. No duplica EMA, SQZMOM,
sincronización temporal ni reglas Strategy 2. Después de cada candidate conserva
las velas setup/confirmation ya vistas y vuelve al estado flat del censo.

Una decisión `APPROVE` se guarda como observación, pero no llama `mark_entry`, no
crea trade, no calcula PnL y no invoca `review_exit`. Por eso el dataset no es un
backtest ni describe una cartera ejecutable.

## Replay y live

Replay es el default. Recorre el bundle completo; cache hits se validan y los
misses se registran `MISSING` sin inventar decisión ni abortar el censo:

```bash
.venv/bin/python -m backtest.strategy_2_run \
  --bundle btcusdt_1d_4h_1h_2026_08 \
  --ai-entry-collect
```

Live requiere simultáneamente `--ai-entry-collect --ai-live` y credenciales.
Usa cache primero y aplica los mismos límites de coste, llamadas y output del
preflight. Este modo no fue ejecutado durante la implementación.

## Identidad, cache y resume

La corrida usa `run_type=entry_collection`, por lo que no puede confundirse con
un full backtest. La cache key no incluye run type ni run ID: fija tipo ENTRY,
payload, provider, model, reasoning, prompt y schema. En consecuencia, una
decisión recogida aquí es reutilizable por el full backtest bajo idéntica
configuración semántica.

Al reanudar el mismo run se reconstruye causalmente la secuencia. Los candidatos
ya cacheados son hits y no generan llamadas ni coste. `PENDING`/`UNKNOWN` bloquea
el candidate afectado y lo registra `UNKNOWN`, sin retry automático.

## Dataset pre-outcome

Por default se escriben CSV y JSON en:

```text
research/output/strategy_2_entry_collection/
```

Cada fila contiene identidad/tiempos/side del candidate, estado AI, confianza,
reason codes, configuración semántica, fuente cache/live, input hash y run ID.
No contiene PnL, MFE, MAE, trade result ni datos futuros.
