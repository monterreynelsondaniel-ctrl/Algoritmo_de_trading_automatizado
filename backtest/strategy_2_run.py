"""Offline/replay Strategy 2 backtest over a frozen MTF bundle."""

import argparse
import json

from ai_decision.service import DecisionService
from ai_decision.store import DecisionStore
from ai_decision.client import OpenAIResponsesClient
from ai_decision.prompts import ENTRY_PROMPT_VERSION, EXIT_PROMPT_VERSION
from ai_decision.schemas import SCHEMA_VERSION
from backtest.strategy_2_engine import Strategy2Backtester
from config import settings
from data.frozen_market_data import FrozenMarketDataStore
from strategies.strategy_2 import Strategy2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--ai-cache", default=settings.ai_cache_path)
    parser.add_argument("--ai-live", action="store_true",
                        help="Allow new paid OpenAI requests; default is cache-only replay")
    args = parser.parse_args()
    market = FrozenMarketDataStore().load_bundle(args.bundle)
    if args.ai_live and not settings.openai_api_key:
        parser.error("--ai-live requires OPENAI_API_KEY")
    mode = "live" if args.ai_live else "replay"
    client = OpenAIResponsesClient(settings.openai_api_key, settings.openai_timeout_seconds) if args.ai_live else None
    ai = DecisionService(client, DecisionStore(args.ai_cache), model=settings.openai_model,
                         provider=settings.ai_provider,
                         reasoning_effort=settings.openai_reasoning_effort, mode=mode,
                         max_attempts=settings.ai_max_attempts)
    result = Strategy2Backtester(Strategy2(), ai).run(market).as_dict()
    result["reproducibility"] = {
        "bundle": args.bundle, "strategy_version": Strategy2().config.version,
        "ai_mode": mode, "model": settings.openai_model,
        "entry_prompt": ENTRY_PROMPT_VERSION, "exit_prompt": EXIT_PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
