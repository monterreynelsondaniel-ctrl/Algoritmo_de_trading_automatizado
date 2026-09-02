# Reporte de Fase 4

## Alcance completado

- Runner por polling para velas cerradas.
- Modos continuo, ciclo único y snapshot totalmente offline.
- Heikin Ashi, SQZMOM y ATR de Wilder en el flujo operativo.
- Deduplicación persistente de todas las velas y decisiones.
- Reconciliación previa a decisiones cuando no se usa dry-run.
- Gestión periódica de breakeven.
- Cierre por señal opuesta sin reversión inmediata.
- Logs obligatorios por ciclo.
- Kill switch persistente entre reinicios.
- Protección contra múltiples runners locales.
- Prueba privada Futures Testnet completamente opt-in.

## Ajustes realizados sobre la propuesta

1. No se implementó trailing stop porque no se definió su algoritmo.
2. Una señal contraria cierra, pero no abre la posición inversa en el mismo
   ciclo; esto reduce riesgo operativo durante el MVP.
3. La deduplicación usa DB y registra también `NONE` y bloqueos.
4. La prueba no cancela todas las órdenes de la cuenta: exige una cuenta
   inicialmente neutra y solo limpia identificadores creados por ella.
5. `finally` realiza limpieza best effort y falla de forma visible si no puede
   confirmar neutralidad.
6. Las órdenes MARKET solicitan respuesta `RESULT` y, si el fill aún no está
   visible, solo se reintenta su consulta, nunca la creación.

## Prueba de integración

La prueba está en `tests/test_binance_integration.py` y no se ejecuta sin:

```text
RUN_BINANCE_INTEGRATION=1
```

Preflight obligatorio:

- Entorno `testnet`.
- Credenciales presentes.
- Trading habilitado y dry-run desactivado.
- One-way Mode.
- Cuenta sin posiciones ni órdenes abiertas.
- Nocional limitado al máximo configurado o al mínimo técnicamente ejecutable.
- Hard cap independiente; la prueba se omite si el mínimo ejecutable lo supera.

La limpieza cancela el stop de la prueba, neutraliza con `reduceOnly` cualquier
posición creada y confirma nuevamente posición cero.

## Validación local

- 35 pruebas offline pasan.
- 1 prueba de integración se omite por defecto.
- Dos ciclos sobre el snapshot produjeron `NO_SIGNAL` y luego
  `DUPLICATE_CANDLE`, confirmando persistencia entre procesos.
- No se realizaron llamadas privadas ni se enviaron órdenes.

## Estado de activación

La infraestructura del MVP está preparada para una primera prueba manual en
Futures Testnet, pero no para producción con dinero real. Debe mantenerse:

```text
BINANCE_ENV=testnet
TRADING_ENABLED=false
DRY_RUN=true
```

hasta configurar una cuenta Testnet dedicada y ejecutar conscientemente la
prueba opt-in.
