# Future scope

These are specified so the paper's "future work" section is concrete. They are not on the demo path. The CVaR helper and the confidential commitment are implemented and tested in `prover/leash-risk/src/future.rs` and are not called by `evaluate`.

## Historical CVaR95

Sort simple returns, average the worst 5% (at least one point). `historical_cvar95` does this. Wiring it into the guest adds a sort and a new public field. Do it only after the MVP experiments are frozen, because it changes the public-values ABI.

## Uniswap v3 slippage inside the guest

Replacing the oracle `minOut` with a tick-bitmap simulation would prove the expected pool output, not just the oracle bound. It needs the pool's tick state as a witness. `sp1-contract-call` can prove that witness against a block hash. This is a second guest program, not a patch on the current one.

## Verify Pyth signatures inside the guest

Tier A (what we shipped) trusts a log of updates that were checked on-chain, which needs a poster. Tier B checks the Wormhole guardian signatures inside the guest with the secp256k1 precompile and drops the log. The tradeoff to measure is prover cycles against the poster's liveness. The poster is one cron script (`services/price_log.py`), not a keeper network, but it is still a moving part.

## Confidential thresholds

`confidential_policy_commitment(policyHash, salt)` hides the numeric limits. The executor would store the salted hash instead of the clear commitment. An adaptive attacker who currently reads `maxWindowLoss` off-chain would have to probe. This is RQ6. It does not stop an attacker who simply drains up to the (unknown) cap; it changes how quickly they can find the cap. The ledger still bounds the loss.

## EIP-7702

The demo account is a deployed contract. EIP-7702 would let an existing EOA delegate to the same validator and executor for one transaction. The modules do not need to change. The account's `execute` entrypoint does.

## RISC Zero as a second backend

The guest is ordinary Rust. A second backend is a port of `program/src/main.rs` onto `risc0-zkvm` and a second verifier address. The experiment is proof time and gas, not a new risk function. Worth doing only as a table in a camera-ready version.
