# zkLeash

An LLM trading agent that cannot move funds unless an SP1 guest proves an EWMA risk check over a Pyth price history, and an ERC-7579 executor plus a loss ledger agree.

This is a final-year research prototype. It runs on Anvil and on testnets with mock tokens. It is not a trading system for real money.

## Layout

| Path | What it is |
| --- | --- |
| `prover/leash-risk` | Fixed-point risk function. Same code the guest runs. |
| `prover/cli` | Execute-mode host: `leash-risk scenario` and `leash-risk check`. |
| `prover/program` | SP1 entrypoint. Not built in CI. |
| `contracts` | Account, validator, executor, price log, ledger, tests. |
| `agent` | Tool-calling agent. Scripted by default. Ollama and Gemini optional. |
| `services` | Orchestrator, price-log cron, demo market maker. |
| `bench` | Harness and gas samples. |
| `dashboard` | Next.js view of the orchestrator. |
| `docs` | Threat model, ABI, risk math, synopsis, report, viva, demo. |
| `paper` | Draft and the submission checklist. |

## Tests

```bash
make test
```

That needs Rust, Foundry, and Python 3.12. `make test` creates `.venv` if it is missing.

Pieces:

```bash
cd prover && cargo test -p leash-risk
cd contracts && forge test
PYTHONPATH=agent .venv/bin/pytest -q agent/tests prover/reference
.venv/bin/python bench/leashbench.py
```

## Local chain

```bash
bash script/e2e_anvil.sh
```

This deploys mock tokens, a mock Pyth, and the mock verifier. The mock verifier does not check proofs. Security tests use `SP1HonestVerifier` inside Foundry instead.

## Orchestrator and dashboard

```bash
.venv/bin/python services/orchestrator.py
cd dashboard && npm install && npm run dev
```

The dashboard talks to `http://127.0.0.1:8000`.

## Proofs on a laptop

Daily work uses execute mode (`leash-risk scenario`), which runs the guest logic and does not prove it. `SP1MockVerifier` is for wiring a deployment. `prover/script/prove.sh` is the Groth16 path, and it expects the Succinct Prover Network. The email asking for academic credits is `docs/outreach/succinct-academic-credits.md`.

## What is not in this tree

The Anvil deploy uses mock tokens and `SP1MockVerifier`. Foundry security tests use `SP1HonestVerifier`, which checks a commitment of the public values, not a Groth16 proof. There is no Base Sepolia deployment and no Prover Network proof in the results. `bench/heldout.json` repeats the same scripted families; it is not an independent held-out set. The paper source is `paper/main.tex`. `paper/SUBMISSION.md` is the checklist for posting it. Nothing has been uploaded to arXiv.

A Base mainnet fork needs your own RPC:

```bash
anvil --fork-url "$BASE_RPC" --fork-block-number "$BASE_BLOCK"
```

Point `PYTH_ADDRESS` and the price ids in `.env.example` at the real feeds before that script is useful. `script/e2e_anvil.sh` is the path that was actually run.

## Reading order

1. `docs/SYNOPSIS.md`
2. `docs/THREAT_MODEL.md` and `docs/RISK_MODEL.md`
3. `paper/main.tex`
4. `docs/DEMO.md` before a viva
