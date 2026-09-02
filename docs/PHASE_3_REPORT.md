# Reporte de Fase 3

## Alcance completado

- Frontera única `OrderExecutor` para entrada, salida y movimiento a breakeven.
- Validación de flags de seguridad, kill switch, posición y modo One-way.
- Entrada MARKET confirmada antes de crear protección.
- Recalculo del stop ATR desde `avgPrice` y cantidad realmente ejecutada.
- STOP_MARKET mediante el servicio Binance Algo actual.
- `reduceOnly=True` obligatorio en stop, salida y emergencia.
- Sustitución segura del stop: primero se coloca la nueva protección y después
  se cancela la anterior.
- Kill switch y cierre de emergencia cuando falla el stop posterior al fill.
- Reconciliación de posiciones y órdenes contra la base local.
- Clasificación verificable entre `STOP_LOSS` y `EXTERNAL_CLOSE`.
- Actualización de precio promedio, comisión y timestamp de reconciliación.

## Correcciones realizadas sobre la propuesta

1. Las mutaciones no se reintentan. Repetir un stop o cierre puede duplicar
   órdenes; los estados inciertos se consultan por su identificador.
2. Binance migró órdenes condicionales de USD-M al servicio Algo. Se utilizan
   `clientAlgoId`, `triggerPrice` y los métodos Algo del SDK instalado.
3. El kill switch es un latch en memoria, no una escritura automática de `.env`.
4. Un cierre sin evidencia del stop se guarda como `EXTERNAL_CLOSE`; nunca se
   atribuye al stop basándose solo en que la posición desapareció.
5. Se exige One-way Mode, ya que el contrato de seguridad depende de
   `reduceOnly`.

## Comportamiento ante fallo de protección

1. El fill de entrada ya está persistido como OPEN.
2. La creación del stop falla o queda sin confirmación.
3. Se registra un evento CRITICAL.
4. El kill switch bloquea futuras intenciones.
5. Se envía un cierre MARKET con `reduceOnly=True`.
6. Si se confirma, el trade queda CLOSED con `EMERGENCY_KILL`.
7. Si tampoco se confirma, el resultado es `UNPROTECTED_KILL_SWITCH` y requiere
   intervención humana inmediata.

## Validación

La suite ejecuta 33 pruebas offline y todas pasan. La cobertura añadida incluye:

- Trading desactivado y dry-run sin mutaciones del SDK.
- Entrada, fill, stop Algo y persistencia.
- Stop recalculado desde el fill real.
- Kill switch y cierre de emergencia reduce-only.
- Salidas explícitas exclusivamente reduce-only.
- Sustitución del stop por breakeven.
- Idempotencia de `clientAlgoId` para órdenes condicionales.
- Cierre local por stop demostrado.
- Cierre externo no atribuible al stop.
- Exposición en Binance sin registro local.

## Límites pendientes

- No se ha enviado ninguna orden privada a Futures Testnet.
- El kill switch aún no sobrevive un reinicio del proceso.
- No existe runner que procese velas, señales y reconciliación periódica.
- No existe migración automática segura desde la tabla prototipo.
- La recuperación de estados PENDING inciertos necesita el runner de la fase
  siguiente.

Por estos límites, `TRADING_ENABLED=false` debe mantenerse hasta completar la
prueba de integración y el ciclo operativo.
