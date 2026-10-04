"""One-turn agent. It proposes an intent. It never signs and never talks to the chain."""

from dataclasses import dataclass, field

from zkleash_agent.market import SimulatedMarket
from zkleash_agent.models import ScriptedModel
from zkleash_agent.schema import Intent
from zkleash_agent.tools import get_news, get_portfolio, get_prices


@dataclass
class Agent:
    model: object = field(default_factory=ScriptedModel)
    market: SimulatedMarket = field(default_factory=SimulatedMarket)

    def observe(self) -> dict:
        return {
            "prices": get_prices(self.market),
            "portfolio": {k: str(v) for k, v in get_portfolio(self.market).items()},
            "news": get_news(self.market),
        }

    def propose(self, user: str) -> Intent:
        return self.model.propose(user, self.market)
