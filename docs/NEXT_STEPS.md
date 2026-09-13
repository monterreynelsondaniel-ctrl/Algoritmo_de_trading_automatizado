# Próximos pasos

1. Revisar y aprobar el presupuesto del preflight antes de habilitar cualquier
   llamada live (`$2.50` y 100 intentos son los límites locales iniciales).
2. Revisar el preflight `strategy2-entry-v2` y decidir explícitamente cómo tratar
   la reserva conservadora `$2.514`, sin elevar límites automáticamente.
3. Sólo con autorización separada, ejecutar y congelar las 81 decisiones V2;
   auditarlas pre-outcome antes de revelar cualquier PnL/MFE/MAE.
4. Diseñar después un análisis de outcomes pre-registrado que compare la selección
   AI sin cambiar prompt, schema, Strategy 2, stop técnico ni reglas de salida;
   predefinir también progreso significativo o time stop. No inventar thresholds
   retrospectivos.
5. Reservar un snapshot futuro no solapado y pre-registrar un único experimento:
   entradas SHORT sólo con alineación `-DI > +DI`, sin umbral ADX ni ATR.
6. Mantener como hipótesis secundaria futura la dinámica ATR exclusiva para
   LONG; no escoger ventana por el mejor resultado histórico.
7. Pre-registrar después invalidación temprana sin seleccionar hora/umbral con
   el snapshot actual.
8. Comparar valores SQZMOM vela por vela contra el Pine Script original.
9. Sustituir la estimación fija por funding histórico real.
10. Investigar después time stop y protección de MFE con reglas predefinidas.
11. Ampliar resolución automática y auditable de estados PENDING inciertos.
12. Añadir adaptador WebSocket sin acoplarlo a estrategia o backtest.
13. Implementar migraciones versionadas antes de conservar datos reales.
14. Ejecutar manualmente la prueba opt-in con una cuenta Futures Testnet dedicada.
