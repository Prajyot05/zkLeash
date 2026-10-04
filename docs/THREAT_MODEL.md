# Threat model

## What the system is for

An LLM proposes a swap. A smart account executes it only if an SP1 proof shows that a fixed risk function, on an authenticated price history, returned allow, and only if the on-chain ledger and post-trade checks also pass.

## Adversary

The adversary can:

- Put arbitrary text in front of the model: the user message, headlines, token metadata, or tool output. The model may then propose any swap or transfer.
- Run the prover. A compromised host can feed the guest any witness it likes.
- Replay an old proof, change calldata after the proof, or submit the same proof on another chain.
- Trade on-chain between proof generation and inclusion, including moving a pool price.
- Split a loss across many individually small trades.
- Steal a baseline's off-chain signing key. zkLeash does not have one.

The adversary cannot:

- Forge a Pyth price update.
- Break SP1 soundness.
- Change the account's installed modules without the owner key.
- Make the session key call anything except `LeashExecutor.executeGuarded`.

## Trusted components

1. SP1 soundness, and the on-chain verifier actually checking the proof. The local `SP1HonestVerifier` is a stand-in that binds the proof to the public values. `SP1MockVerifier` does not, and is not a security mechanism.
2. Pyth prices stay within the confidence band the policy allows. A wrong but valid Pyth price is a trusted-input failure, same as in every oracle design.
3. The account, the executor, the price log, and the ledger are the code that was audited and installed. The owner key that installs them is trusted.
4. Allowlisted routers do what their ABI says. A malicious router that the owner allowlisted can still take tokens. The allowlist is a policy choice, not a proof.

## What is untrusted

The model, its prompt, its tools, the machine that runs the prover, and every byte the prover claims about prices or balances. The contract re-derives the action hash, checks price-log heads, checks live balances, and checks the Pyth price against the proven price.

## Assumptions used by the bounded-damage claim

- A1. A valid proof implies the guest ran `evaluate` on the committed public values.
- A2. A recorded price was accepted by Pyth.
- A3. The account only lets the executor move funds, and the executor is the deployed bytecode.
- A4. If the price log is not posted, trades fail closed. Liveness depends on the poster. Safety does not.

Under those assumptions, a sequence of session-key trades in a window cannot push realized loss above `maxWindowLoss`, and no executed trade exceeds the volatility, concentration, notional, or slippage limits. The Foundry invariant test checks the ledger half of this. The guest tests check the volatility half. This is an informal argument plus those tests, not a machine-checked proof.
