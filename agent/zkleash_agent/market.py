"""A seeded price path the agent and the tests can share. Not a source of truth for the proof."""

from dataclasses import dataclass, field


@dataclass
class SimulatedMarket:
    prices: dict[str, float] = field(default_factory=lambda: {"WETH": 2000.0, "USDC": 1.0})
    balances: dict[str, int] = field(
        default_factory=lambda: {"WETH": 10 * 10**18, "USDC": 20_000 * 10**6}
    )
    headlines: list[str] = field(
        default_factory=lambda: ["ETH funding is flat.", "USDC peg is holding."]
    )
    step_n: int = 0

    def tick(self, shock: float = 0.0) -> None:
        self.step_n += 1
        self.prices["WETH"] *= 1.0 + shock
        if self.prices["WETH"] <= 0:
            self.prices["WETH"] = 1.0

    def poison(self, text: str) -> None:
        self.headlines.append(text)
