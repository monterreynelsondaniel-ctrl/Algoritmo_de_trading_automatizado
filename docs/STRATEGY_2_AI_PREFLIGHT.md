# Preflight AI de Strategy 2

Fecha: 2026-09-09. Estado: operativo, offline; no se realizaron llamadas OpenAI.

## Configuración auditada

- Provider: `openai`.
- Modelo: `gpt-5.6-terra` (configurable; no pertenece a Strategy 2).
- Reasoning: `low`.
- Modo predeterminado: `replay`.
- Prompts: `strategy2-entry-v1` y `strategy2-exit-v1`.
- Schema: `1.0.0`.
- Timeout: 30 s; SDK con retries desactivados; aplicación hasta 2 intentos sólo
  cuando el error no deja incierto el estado de la respuesta.
- Cache/auditoría/runs: SQLite local en `database/ai_decisions.db`.

`OPENAI_API_KEY` es la variable consumida por `Settings` y entregada al SDK sólo
en modo live. El campo queda excluido de `repr`; no se serializa en cache, runs,
auditoría ni reportes. `.env` está ignorado por Git.

## Workload offline

Bundle: `btcusdt_1d_4h_1h_2026_08`.

El censo causal, manteniendo siempre el mercado plano y sin asignar APPROVE o
REJECT, encontró 81 candidatos: 18 LONG y 63 SHORT. Es una estimación de ENTRY
reviews potenciales, no un resultado de estrategia.

EXIT depende de decisiones todavía inexistentes. Sus límites son:

- mínimo: 0 (ninguna entrada aprobada);
- escenario de capacidad: 810 (10 revisiones 4H por candidato, supuesto de
  planificación, no regla de salida);
- techo estructural: 2.145 cierres 4H evaluables. La regla de posición única
  impide más de una revisión EXIT por evento 4H.

## Tokens y coste

No está instalado un tokenizer específico para Terra. La estimación offline usa
el prompt, JSON real y JSON Schema con un divisor conservador de 3,5 caracteres
por token. Para el coste esperado se usan 300 tokens de salida; el límite live
es 2.000 porque también debe alojar razonamiento interno, y se reserva completo
antes de llamar. Para que el budget sea fail-closed sin tokenizer, el input
ceiling cuenta un token por byte UTF-8: deliberadamente sobreestima el consumo.

| Review | Input estimado | Input ceiling | Output esperado | Coste esperado | Reserva máxima |
|---|---:|---:|---:|---:|---:|
| ENTRY | 606 | 2.118 | 300 | $0.004812 | $0.028236 |
| EXIT representativo | 666 | 2.331 | 300 | $0.004932 | $0.028662 |

Se usó la tarifa oficial de Terra vigente al 2026-09-09: $2/M input y $12/M
output. La corrida ENTRY completa se estima en $0.389772 y reservaría como techo
$2.287116. El escenario de capacidad ENTRY+EXIT se estima en $4.384692; el techo
estructural absoluto usa la reserva de 2.000 tokens por respuesta y se obtiene
en $63.767106. El usage real reemplaza la reserva cuando el
proveedor lo devuelve. La cache SQLite local cuesta cero llamadas.

Fuente oficial: [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra).

## Límites y reanudación

Defaults que requieren aprobación antes de live:

```text
AI_MAX_RUN_COST_USD=2.5
AI_MAX_LIVE_CALLS_PER_RUN=100
AI_MAX_OUTPUT_TOKENS_PER_CALL=2000
```

El presupuesto se reserva antes de cada intento nuevo. Alcanzarlo aborta sin
crear una decisión y jamás equivale a APPROVE. Los cache hits no cuentan.

Cada `run_id` fija strategy version, bundle/hash, provider/model/reasoning,
prompts, schema y modo. Se guarda status, timestamps, último evento y contadores.
El ledger conserva por separado coste reservado/estimado y coste calculado con
el usage real; si una llamada queda incierta, la reserva permanece por seguridad.
La reanudación reproduce causalmente desde el bundle y consume decisiones ya
cacheadas; así reconstruye setup, candidate, posición, bars/MFE/MAE sin duplicar
todo el estado. Un cambio semántico obliga a iniciar otro run.

Antes de llamar se persiste `PENDING`; cachear respuesta, cerrar pending y
auditar ocurre en una transacción. Si hay timeout/conexión, pasa a `UNKNOWN` y
se bloquea el reintento automático. Una caída exacta después de la respuesta y
antes del commit sigue siendo imposible de resolver automáticamente con
`store=False`: quedará pending y requerirá auditoría humana. Esto privilegia no
duplicar cobro sobre continuidad automática.

## Comando seguro

```bash
.venv/bin/python -m backtest.strategy_2_run \
  --bundle btcusdt_1d_4h_1h_2026_08 \
  --ai-preflight
```

Muestra bundle/hash, configuración, candidatos, cache, tokens, costes, límites
y estado opcional de `--run-id`. No instancia el cliente OpenAI.

Este modo sólo estima. La recolección real de decisiones ENTRY se realiza con
`--ai-entry-collect`; el backtest path-dependent sigue siendo el modo sin flags.
Consulta `STRATEGY_2_ENTRY_COLLECTION.md` para las fronteras exactas.
