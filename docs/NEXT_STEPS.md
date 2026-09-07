# Próximos pasos

1. Diseñar Strategy 2 sobre el contrato existente, definiendo primero cómo
   sincronizar 1D/4H/1H sin introducir lookahead; todavía no implementarla.
2. Reservar un snapshot futuro no solapado y pre-registrar un único experimento:
   entradas SHORT sólo con alineación `-DI > +DI`, sin umbral ADX ni ATR.
3. Mantener como hipótesis secundaria futura la dinámica ATR exclusiva para
   LONG; no escoger ventana por el mejor resultado histórico.
4. Pre-registrar después invalidación temprana sin seleccionar hora/umbral con
   el snapshot actual.
5. Comparar valores SQZMOM vela por vela contra el Pine Script original.
6. Sustituir la estimación fija por funding histórico real.
7. Investigar después time stop y protección de MFE con reglas predefinidas.
8. Ampliar resolución automática y auditable de estados PENDING inciertos.
9. Añadir adaptador WebSocket sin acoplarlo a estrategia o backtest.
10. Implementar migraciones versionadas antes de conservar datos reales.
11. Ejecutar manualmente la prueba opt-in con una cuenta Futures Testnet dedicada.
