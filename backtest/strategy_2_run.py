"""Offline/replay Strategy 2 backtest over a frozen MTF bundle."""

import argparse
import json

from ai_decision.service import DecisionService
from ai_decision.store import DecisionStore
from ai_decision.client import OpenAIResponsesClient
from ai_decision.budget import RunBudget
from ai_decision.prompts import ENTRY_PROMPT_VERSION, EXIT_PROMPT_VERSION
from ai_decision.runs import AIRunIdentity, AIRunManager
from ai_decision.schemas import SCHEMA_VERSION
from backtest.strategy_2_engine import Strategy2Backtester
from backtest.strategy_2_preflight import bundle_fingerprint, create_preflight_report
from config import settings
from data.frozen_market_data import FrozenMarketDataStore
from strategies.strategy_2 import Strategy2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--ai-cache", default=settings.ai_cache_path)
    parser.add_argument("--ai-live", action="store_true",
                        help="Allow new paid OpenAI requests; default is cache-only replay")
    parser.add_argument("--ai-preflight", action="store_true",
                        help="Offline workload/cost preview; never calls OpenAI")
    parser.add_argument("--run-id", help="Resume an existing compatible run")
    args = parser.parse_args()
    store = DecisionStore(args.ai_cache)
    if args.ai_preflight:
        report = create_preflight_report(args.bundle, store, settings).as_dict()
        report["mode"] = "preflight_offline"
        report["prompt_versions"] = {"entry": ENTRY_PROMPT_VERSION, "exit": EXIT_PROMPT_VERSION}
        report["schema_version"] = SCHEMA_VERSION
        report["limits"] = {
            "max_run_cost_usd": settings.ai_max_run_cost_usd,
            "max_live_calls_per_run": settings.ai_max_live_calls_per_run,
            "max_output_tokens_per_call": settings.ai_max_output_tokens_per_call,
        }
        report["resume_status"] = None if not args.run_id else store.get_run(args.run_id)
        print(json.dumps(report, indent=2))
        return
    market = FrozenMarketDataStore().load_bundle(args.bundle)
    if args.ai_live and not settings.openai_api_key:
        parser.error("--ai-live requires OPENAI_API_KEY")
    mode = "live" if args.ai_live else "replay"
    client = OpenAIResponsesClient(settings.openai_api_key, settings.openai_timeout_seconds) if args.ai_live else None
    identity = AIRunIdentity(
        strategy_version=Strategy2().config.version, bundle_name=args.bundle,
        bundle_hash=bundle_fingerprint(args.bundle), provider=settings.ai_provider,
        model=settings.openai_model, reasoning_effort=settings.openai_reasoning_effort,
        entry_prompt_version=ENTRY_PROMPT_VERSION, exit_prompt_version=EXIT_PROMPT_VERSION,
        schema_version=SCHEMA_VERSION, ai_mode=mode,
    )
    run_manager = AIRunManager(store, identity, args.run_id)
    run_manager.start()
    budget = RunBudget(
        run_manager, max_cost_usd=settings.ai_max_run_cost_usd,
        max_live_calls=settings.ai_max_live_calls_per_run,
        max_output_tokens=settings.ai_max_output_tokens_per_call,
        input_cost_per_million=settings.ai_input_cost_per_million_usd,
        output_cost_per_million=settings.ai_output_cost_per_million_usd,
    )
    ai = DecisionService(client, store, model=settings.openai_model,
                         provider=settings.ai_provider,
                         reasoning_effort=settings.openai_reasoning_effort, mode=mode,
                         max_attempts=settings.ai_max_attempts, budget=budget,
                         run_manager=run_manager,
                         max_output_tokens=settings.ai_max_output_tokens_per_call)
    try:
        result = Strategy2Backtester(Strategy2(), ai).run(market).as_dict()
    except KeyboardInterrupt:
        run_manager.interrupt({"error_type": "KeyboardInterrupt"})
        raise
    except Exception as error:
        run_manager.fail({"error_type": type(error).__name__})
        raise
    run_manager.complete()
    result["run"] = run_manager.record()
    result["reproducibility"] = {
        "bundle": args.bundle, "strategy_version": Strategy2().config.version,
        "ai_mode": mode, "model": settings.openai_model,
        "entry_prompt": ENTRY_PROMPT_VERSION, "exit_prompt": EXIT_PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
