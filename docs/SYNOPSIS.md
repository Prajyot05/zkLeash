# Synopsis

**Title.** zkLeash: trustless, stateful risk enforcement for LLM trading agents.

**Degree.** B.Tech. final-year project.

## Problem

Language-model agents are being wired to crypto wallets. The model can be prompt-injected, and it cannot be relied on for arithmetic. A signature from the agent is not a safety argument. Recent systems (PACE, Proof-Gated Signing) put a deterministic checker in front of the wallet, but the checker is trusted: it holds a key, or it holds the key's signer. They also judge one transaction at a time, so a sequence of individually allowed trades can still drain the account. Checks that only look at the current price cannot see that the asset being bought is volatile.

## Objective

Build and evaluate an account that executes an agent's swap only when:

1. an SP1 proof shows a fixed EWMA risk function accepted the post-trade portfolio,
2. the prices in that proof match a Pyth-verified on-chain history,
3. a ledger caps execution loss (value given up against the oracle price) across the sequence.

No off-chain signing key can wave a trade through.

## Method

- Guest: fixed-point EWMA and a volatility-scaled exposure limit, in Rust, run natively and in the SP1 executor on a laptop. Groth16 wrapping is reserved for the Succinct Prover Network.
- Contracts: an ERC-7579 validator and executor on a minimal ERC-4337 account, a Pyth pull inside the trade, an append-only price log, and a loss ledger. Cheap checks stay in Solidity.
- Evaluation: Foundry tests for the contract rules, including a forged history, a tampered proof, a salami sequence, and a stolen-key baseline. A randomized 225-trial harness (nine families, 25 seeds each) compares five baselines and records which check denies each trade. Gas for the same EWMA in Solidity is measured at four window lengths, reading prices from calldata and from storage.

## Expected outcome

On the harness, zkLeash blocks every harmful trial and none of the benign ones. The stateless and static baselines miss the salami family, and the static cap also misses volatility-spike buys and blocks de-risking sales. The signed baseline misses the salami family and any trial where its key is stolen. The contribution a reviewer can attack is this comparison, not a claim of a new trading strategy.

## Team split

Person 1 owns the agent, the harness, and the dashboard. Person 2 owns the guest. Person 3 owns the contracts. The public-values layout in `docs/PUBLIC_VALUES.md` is the interface they share.
