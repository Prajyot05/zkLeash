# Project report

**zkLeash: trustless, stateful risk enforcement for LLM trading agents.**

## 1. Summary

The project is a trading agent that cannot move funds unless a proof and an on-chain ledger agree. The agent is a tool-calling loop. The proof is an SP1 guest that computes EWMA volatility over Pyth prices. The account is an ERC-4337 contract with an ERC-7579 validator and executor. Development runs the guest logic natively on laptops; the compiled guest has also been run in the SP1 executor. A Base Sepolia deployment script is included; the live demo uses Anvil or Sepolia mock tokens, not mainnet funds.

## 2. What was built

- `prover/leash-risk`: fixed-point risk function, hash chain, public-value encoder, CVaR and confidential-commitment helpers that the guest does not call.
- `prover/cli`: `leash-risk check` and `leash-risk scenario`.
- `prover/program`: SP1 entrypoint, built only when the SP1 toolchain is installed.
- `prover/exec`: runs the guest ELF in the SP1 executor and checks its public values against native `evaluate`.
- `contracts`: executor, validator, account, price log, ledger, two baselines, an on-chain EWMA used for the gas study, Foundry tests.
- `agent`: scripted model plus optional Ollama and Gemini clients.
- `services`: FastAPI orchestrator, price-log poster, demo payout script.
- `bench`: 250-trial randomized comparison, the August 2024 price replay, gas samples, and figures.
- `dashboard`: a local view of the orchestrator feed.
- `zkLeash_IEEE_paper_v3.docx`: the paper, built by `make paper`; `paper/REVIEW.md` is the review behind it. `paper/main.tex` is an older draft.

## 3. Results

Contract tests: 20 passing, plus an invariant of 128,000 handler calls that never stored a window loss above the cap. Rust: 13 unit tests.

Harness, 250 randomized trials in ten families. Seventy-five harmful trials are structural and are not in the measured rate. Measured attack success on the other 75: unguarded 75/75, keyword filter 67/75, static cap 50/75, signed attestation 25/75, stateless proof 25/75, daily notional cap 0/75, zkLeash 0/75 (95% Clopper-Pearson upper bound 4.8%). False blocks out of 100 benign trials: daily notional cap 35, static cap 25, zkLeash 7 (all from the 20-trade cap), and 0 for the others. The stateless proof misses the salami drain (up to $1,419 against a $400 cap). The daily cap stops it at about $42 of loss and also blocks benign turnover. Details are in `bench/results/summary.json` and in the paper. A separate case study replays Binance ETH-USDT hourly closes through the August 5, 2024 unwind.

EWMA gas for one asset, reading prices from storage: 36,116 (8 prices), 114,694 (32), 219,469 (64), 429,031 (128); from unauthenticated calldata: 18,873 to 182,510. A later guarded trade costs 260,218 gas with the stand-in verifier. SP1 executor: 334,624 cycles at 8 prices per asset, 4,453,756 at 256, public values identical to native execution.

## 4. How to reproduce

See the root `README.md`. `make test` runs the Rust tests, the Foundry suite, the Python tests, and the harness.

## 5. Division of work

The repository is one tree. The intended split is in `docs/SYNOPSIS.md`: agent and harness, guest, contracts. The public-values document is the contract between them.

## 6. Limits

No Groth16 proof was generated here. No live LLM was scored in the harness. The held-out file is not independent. The account is a teaching implementation of the 7579 call path, not a production Kernel deployment. Testnet prices in the demo are mock prices. Evaluation of economic performance (Sharpe, drawdown) was not run.

## 7. Ethics

The system is for testnet and local demonstration. It is not an invitation to trade real funds, and the report should not be read as investment advice.
