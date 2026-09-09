"""Local, fail-closed accounting for paid AI calls."""

import math


class AIBudgetExceededError(RuntimeError):
    pass


def estimate_tokens(*values) -> int:
    """Conservative offline estimate; no model tokenizer is bundled."""
    characters = sum(len(value) for value in values)
    return max(1, math.ceil(characters / 3.5))


def conservative_token_upper_bound(*values) -> int:
    """Tokenizer-independent ceiling: a token cannot encode less than one byte."""
    return max(1, sum(len(value.encode("utf-8")) for value in values))


def token_cost(input_tokens, output_tokens, input_per_million, output_per_million):
    return (input_tokens * input_per_million + output_tokens * output_per_million) / 1_000_000


class RunBudget:
    def __init__(self, run_manager, *, max_cost_usd, max_live_calls, max_output_tokens,
                 input_cost_per_million, output_cost_per_million):
        self.run_manager = run_manager
        self.max_cost_usd = float(max_cost_usd)
        self.max_live_calls = int(max_live_calls)
        self.max_output_tokens = int(max_output_tokens)
        self.input_price = float(input_cost_per_million)
        self.output_price = float(output_cost_per_million)

    def cache_hit(self):
        self.run_manager.increment(cache_hits=1)

    def authorize(self, input_tokens):
        counters = self.run_manager.counters()
        reserved_cost = token_cost(
            input_tokens, self.max_output_tokens, self.input_price, self.output_price
        )
        if counters["live_calls"] + 1 > self.max_live_calls:
            raise AIBudgetExceededError("AI_MAX_LIVE_CALLS_PER_RUN would be exceeded")
        if counters["estimated_cost_usd"] + reserved_cost > self.max_cost_usd:
            raise AIBudgetExceededError("AI_MAX_RUN_COST_USD would be exceeded")
        self.run_manager.increment(
            live_calls=1,
            input_tokens=input_tokens,
            output_tokens=self.max_output_tokens,
            estimated_cost_usd=reserved_cost,
        )

    def reconcile_usage(self, input_tokens, usage):
        if not isinstance(usage, dict):
            return
        actual_input = usage.get("input_tokens")
        actual_output = usage.get("output_tokens")
        if not isinstance(actual_input, int) or not isinstance(actual_output, int):
            return
        reserved = token_cost(input_tokens, self.max_output_tokens, self.input_price, self.output_price)
        actual = token_cost(actual_input, actual_output, self.input_price, self.output_price)
        self.run_manager.increment(
            input_tokens=actual_input - input_tokens,
            output_tokens=actual_output - self.max_output_tokens,
            estimated_cost_usd=actual - reserved,
            actual_cost_usd=actual,
        )
