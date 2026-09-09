# Próximos pasos

1. Aprobar el versionado explícito del bundle congelado BTCUSDT 1D/4H/1H ya
   validado, manteniendo el allowlist estricto de snapshots.
2. Ejecutar un lote AI pequeño y controlado para poblar cache; registrar modelo,
   prompts, schema, uso y costo, y luego reproducirlo completamente en replay.
3. Analizar candidates aprobados/rechazados antes de definir stop técnico,
   progreso significativo o time stop. No inventar thresholds retrospectivos.
4. Reservar un snapshot futuro no solapado y pre-registrar un único experimento:
   entradas SHORT sólo con alineación `-DI > +DI`, sin umbral ADX ni ATR.
5. Mantener como hipótesis secundaria futura la dinámica ATR exclusiva para
   LONG; no escoger ventana por el mejor resultado histórico.
6. Pre-registrar después invalidación temprana sin seleccionar hora/umbral con
   el snapshot actual.
7. Comparar valores SQZMOM vela por vela contra el Pine Script original.
8. Sustituir la estimación fija por funding histórico real.
9. Investigar después time stop y protección de MFE con reglas predefinidas.
10. Ampliar resolución automática y auditable de estados PENDING inciertos.
11. Añadir adaptador WebSocket sin acoplarlo a estrategia o backtest.
12. Implementar migraciones versionadas antes de conservar datos reales.
13. Ejecutar manualmente la prueba opt-in con una cuenta Futures Testnet dedicada.
