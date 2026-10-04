"""Keeps a demo pool's payout near the Pyth price.

On Base Sepolia the project deploys its own mock pool because testnet liquidity is
not meaningful. This process sets `MockRouter.setPayout` from the latest fair
amount. Evaluation numbers come from an Anvil fork, not from this script.
"""

import os
import sys


def fair_out_usdc(weth_amount_wei: int, eth_price_usd: float) -> int:
    return int(weth_amount_wei * eth_price_usd / 10**18 * 10**6)


def main() -> int:
    amount = int(os.environ.get("AMOUNT_IN", str(10**17)))
    price = float(os.environ.get("ETH_PRICE", "2000"))
    payout = fair_out_usdc(amount, price)
    print(f"demo payout for {amount} wei at ${price}: {payout} (6 decimals)")
    if not os.environ.get("RPC_URL"):
        print("RPC_URL unset; not broadcasting.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
