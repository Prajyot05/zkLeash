# Viva notes

Questions the panel is likely to ask, and the answer that matches what the code does.

**Why not just use a spending limit?**
A spending limit is baseline B2. It stops a single huge transfer. It does not stop ten small losses, and it does not know that the asset being bought is the volatile one. The salami row in the paper is that gap.

**Why ZK if the contract recomputes the exposure sum?**
The contract recomputes the sum from sigmas the proof commits to. It does not recompute the sigmas. Those need the price window. Doing that in Solidity is the gas table: 171k gas at 128 prices for one asset, and it scales with the window.

**What if the prover lies about the prices?**
The public values include the hash-chain heads. The executor compares them to `PriceHistoryLog`, which only appends a price Pyth has already checked. The test is `test_forged_price_history_is_rejected`.

**What if someone tampers with the proof?**
Against the honest verifier, the proof bytes are bound to the public values. The test flips one byte and expects `BadProof`. The mock verifier does not do this. We do not use it for security claims. A real deployment uses SP1's Groth16 verifier.

**You did not produce a Groth16 proof. Is the project unfinished?**
The risk function and the contract checks are finished and tested. Groth16 is a wrapping step we deliberately kept off student laptops. `prover/script/prove.sh` is that step, on the Prover Network, for the demo. The compiled guest has been run in the SP1 executor (`make sp1-cycles`), and its public values are byte-identical to the native function the harness uses.

**Where is the p-value?**
There is none. Each of the 225 trials is a different random draw, and the intervals are exact Clopper-Pearson intervals per family and overall. zkLeash's advantage on the salami family is structural, so a significance test adds nothing. The attacker is scripted, so the intervals do not say how often a new model would fail in the wild. Say that before anyone else does.

**What did you not build?**
Historical CVaR inside the guest, Uniswap v3 simulation, in-guest Pyth signature checks, hidden thresholds, EIP-7702, a second zkVM. They are written up in `docs/FUTURE_SCOPE.md`. CVaR and the salted commitment exist as tested functions and are not on the execution path.
