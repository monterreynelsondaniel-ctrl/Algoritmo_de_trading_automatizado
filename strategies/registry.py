"""Small explicit strategy registry; intentionally contains only Strategy 1."""

from strategies.strategy_1 import Strategy1


_STRATEGIES = {"strategy_1": Strategy1}


def available_strategies() -> tuple[str, ...]:
    return tuple(_STRATEGIES)


def get_strategy(name: str = "strategy_1"):
    try:
        strategy_type = _STRATEGIES[name]
    except KeyError as error:
        choices = ", ".join(available_strategies())
        raise ValueError(f"Unknown strategy {name!r}. Available: {choices}") from error
    return strategy_type()
