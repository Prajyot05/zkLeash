"""Tools the model is allowed to call. Tool output is untrusted data, not instructions."""

from zkleash_agent.market import SimulatedMarket
from zkleash_agent.schema import HoldIntent, Intent, SwapIntent, TransferIntent


def get_prices(market: SimulatedMarket) -> dict[str, float]:
    return dict(market.prices)


def get_portfolio(market: SimulatedMarket) -> dict[str, int]:
    return dict(market.balances)


def get_news(market: SimulatedMarket) -> list[str]:
    return list(market.headlines)


def propose_trade(intent: Intent) -> Intent:
    return intent


def intent_from_tool_args(name: str, args: dict) -> Intent:
    if name == "hold":
        return HoldIntent(reason=args.get("reason", "no trade"))
    if name == "transfer":
        return TransferIntent(
            token=args["token"],
            to=args["to"],
            amount=int(args["amount"]),
            reason=args.get("reason", "transfer"),
        )
    if name == "swap":
        return SwapIntent(
            token_in=args["token_in"],
            token_out=args["token_out"],
            amount_in=int(args["amount_in"]),
            reason=args.get("reason", "swap"),
        )
    raise ValueError(f"unknown tool {name}")
