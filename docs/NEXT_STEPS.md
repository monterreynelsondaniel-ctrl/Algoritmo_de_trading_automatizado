# Próximos pasos

1. Reservar un snapshot futuro no solapado antes de evaluar otra variante de
   régimen de volatilidad; el filtro ATR `<=1.0` quedó rechazado en desarrollo.
2. Pre-registrar el próximo experimento de invalidación temprana sin seleccionar
   hora/umbral con el snapshot actual.
3. Comparar valores SQZMOM vela por vela contra el Pine Script original.
4. Sustituir la estimación fija por funding histórico real.
5. Investigar después time stop y protección de MFE con reglas predefinidas.
6. Ampliar resolución automática y auditable de estados PENDING inciertos.
7. Añadir adaptador WebSocket sin acoplarlo a estrategia o backtest.
8. Implementar migraciones versionadas antes de conservar datos reales.
9. Ejecutar manualmente la prueba opt-in con una cuenta Futures Testnet dedicada.
