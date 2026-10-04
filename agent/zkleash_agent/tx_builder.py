"""Map an intent onto the guest's scenario interface.

A transfer has no guest encoding: the builder reports it as unleashable, which the
executor also rejects because the router is not allowlisted.
"""

from zkleash_agent.schema import HoldIntent, Intent, SwapIntent, TransferIntent


def build(intent: Intent) -> dict:
    if isinstance(intent, HoldIntent):
        return {"status": "hold", "reason": intent.reason}
    if isinstance(intent, TransferIntent):
        return {
            "status": "unleashable",
            "reason": "raw transfers are not an allowlisted action",
            "intent": intent.model_dump(),
        }
    if isinstance(intent, SwapIntent):
        scenario = "calm"
        if intent.token_in == "USDC" and intent.amount_in >= 20_000 * 10**6:
            scenario = "volatile_buy"
        return {
            "status": "needs_proof",
            "scenario": scenario,
            "token_in": intent.token_in,
            "token_out": intent.token_out,
            "amount_in": str(intent.amount_in),
            "reason": intent.reason,
        }
    raise TypeError(type(intent))
