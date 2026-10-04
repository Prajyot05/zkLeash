# Project report

**zkLeash: trustless, stateful risk enforcement for LLM trading agents.**

## 1. Summary

The project is a trading agent that cannot move funds unless a proof and an on-chain ledger agree. The agent is a tool-calling loop. The proof is an SP1 guest that computes EWMA volatility over Pyth prices. The account is an ERC-4337 contract with an ERC-7579 validator and executor. Development runs on laptops in execute mode. A Base Sepolia deployment script is included; the live demo uses Anvil or Sepolia mock tokens, not mainnet funds.

## 2. What was built

- `prover/leash-risk`: fixed-point risk function, hash chain, public-value encoder, CVaR and confidential-commitment helpers that the guest does not call.
- `prover/cli`: `leash-risk check` and `leash-risk scenario`.
- `prover/program`: SP1 entrypoint, built only when the SP1 toolchain is installed.
- `contracts`: executor, validator, account, price log, ledger, two baselines, an on-chain EWMA used for the gas study, Foundry tests.
- `agent`: scripted model plus optional Ollama and Gemini clients.
- `services`: FastAPI orchestrator, price-log poster, demo payout script.
- `bench`: 60-trial comparison and the gas samples.
- `dashboard`: a local view of the orchestrator feed.
- `paper/main.tex`: the draft.

## 3. Results

Contract tests: 16 passing, plus an invariant of 128,000 handler calls that never stored a window loss above the cap.

Harness, 50 harmful trials: unguarded attack success 1.00; keyword filter 0.90; static cap 0.20; signed attestation 0.40; stateless proof 0.20; zkLeash 0.00. Benign rebalances: no false blocks. The only family the stateless proof misses, and the signed baseline also misses, is the salami drain. Details and intervals are in `bench/results/summary.json` and in the paper.

EWMA gas: 17,935 (8 prices), 50,591 (32), 90,822 (64), 171,360 (128).

## 4. How to reproduce

See the root `README.md`. `make test` runs the Rust tests, the Foundry suite, the Python tests, and the harness.

## 5. Division of work

The repository is one tree. The intended split is in `docs/SYNOPSIS.md`: agent and harness, guest, contracts. The public-values document is the contract between them.

## 6. Limits

No Groth16 proof was generated here. No live LLM was scored in the 60 trials. The held-out file is not independent. The account is a teaching implementation of the 7579 call path, not a production Kernel deployment. Testnet prices in the demo are mock prices. Evaluation of economic performance (Sharpe, drawdown) was not run.

## 7. Ethics

The system is for testnet and local demonstration. It is not an invitation to trade real funds, and the report should not be read as investment advice.
