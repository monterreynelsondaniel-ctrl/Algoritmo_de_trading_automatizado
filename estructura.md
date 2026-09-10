# Estructura del proyecto

```text
.
├── backtest
│   ├── engine.py
│   ├── run.py
│   ├── strategy_2_engine.py
│   ├── strategy_2_candidates.py
│   ├── strategy_2_entry_collector.py
│   ├── strategy_2_preflight.py
│   ├── strategy_2_run.py
│   └── statistics.py
├── ai_decision
│   ├── client.py
│   ├── budget.py
│   ├── prompts.py
│   ├── schemas.py
│   ├── service.py
│   ├── store.py
│   └── runs.py
├── config.py
├── data
│   ├── frozen_market_data.py
│   └── snapshots/
├── database
│   ├── database.py
│   ├── migrations/README.md
│   ├── models.py
│   ├── state_service.py
│   └── trade_service.py
├── docs
│   ├── DECISIONS.md
│   ├── NEXT_STEPS.md
│   ├── STRATEGY_2_AI_PREFLIGHT.md
│   ├── STRATEGY_2_ENTRY_COLLECTION.md
│   ├── PHASE_2_REPORT.md
│   ├── PROGRESS_REPORT_2026-08-31.md
│   └── PROJECT_CONTEXT.md
├── exchange
│   ├── binance_client.py
│   ├── exceptions.py
│   ├── multi_timeframe.py
│   └── market_data.py
├── execution
│   ├── order_executor.py
│   ├── process_lock.py
│   └── safety.py
├── logs
│   └── logger.py
├── positions
│   ├── manager.py
│   └── reconciliation.py
├── strategies
│   ├── __init__.py
│   ├── base.py
│   ├── candles.py
│   ├── confidence.py
│   ├── indicators.py
│   ├── registry.py
│   ├── signals.py
│   ├── squeeze_strategy.py
│   ├── strategy_1
│   │   ├── __init__.py
│   │   ├── signals.py
│   │   └── strategy.py
│   └── strategy_2
│       ├── config.py
│       ├── models.py
│       ├── rules.py
│       └── strategy.py
├── tests
│   ├── test_backtest_fees.py
│   ├── test_binance_client.py
│   ├── test_binance_integration.py
│   ├── test_candles.py
│   ├── test_config.py
│   ├── test_engine.py
│   ├── test_frozen_market_data.py
│   ├── test_positions_manager.py
│   ├── test_order_executor.py
│   ├── test_reconciliation.py
│   ├── test_runner.py
│   ├── test_statistics.py
│   ├── test_strategy_2_entry_collector.py
│   └── test_trade_service.py
├── .env.example
├── run_testnet.py
├── README.md
└── requirements.txt
```

Las responsabilidades y decisiones vigentes se documentan en `docs/`.
