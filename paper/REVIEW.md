# Review of `zkLeash_IEEE_paper_revised.docx`

Reviewed against the repository at commit `4efe29d`. Every claim in the paper was checked against the code, the Foundry tests, and `bench/results/*.json`. Findings are ordered by how likely they are to cost the paper a rejection.

The design sections hold up. The 52-word public values, the action-hash and policy-commitment fields, the order of the execution checks, the limits (80% concentration, 30% drawdown, 1% slippage, 0.5% live-price band, 20 trades per window), the EWMA worked example (`34117444218463961`), the gas samples, the 16 Foundry tests plus a 128,000-call invariant (256 runs x depth 500), and every number in Table III match the repository. The problems are in how the evaluation was produced and reported, and in four security statements.

Section "Status after revision" at the end records what was changed in `zkLeash_IEEE_paper_v3.docx` and in the code.

---

## Critical

### C1. The statistics count deterministic repeats as independent trials

**Where.** Sec. VII-A ("Confidence intervals come from bootstrap resampling ... McNemar's test"), Sec. VII-B ("McNemar's test gives p ≈ 0.004").

**Evidence.** `bench/leashbench.py` runs `for seed in range(10)`, but no input depends on the seed except the wording of `direct_transfer` (`seed % 2`). Guest results are memoised in `_GUEST_CACHE`, so seeds 1 to 9 return seed 0's answer. The 60 trials are about 7 distinct cases. The summary file's own `note` says "Seeds repeat a deterministic attacker".

**Why it matters.** A bootstrap over ten copies of one outcome yields [0, 0] or [1, 1]. McNemar's b = 10, c = 0 is one discordant case counted ten times. Any reviewer who opens the harness will see pseudo-replication.

**Fix.** Generate the trials from a seeded random process (price path, volatility regime, trade size, balances, number of salami legs), so that each seed is a different input. Report per-family outcomes with exact Clopper-Pearson intervals over those genuinely distinct trials. Drop McNemar: zkLeash's advantage on the salami family is structural, and a p-value adds nothing.

### C2. Three of the five harmful families have zkLeash's outcome hard-coded

**Where.** Table III, abstract ("zkLeash stopped every harmful trial").

**Evidence.** In `run_case`, `direct_transfer`, `illiquid_pool`, and `stolen_key` call `_row(..., leash_blocks=True, proof=None, ...)`. The guest is never run for these families. `stolen_key` also forces `row["systems"]["B3_signed"] = False`.

**Why it matters.** 30 of the 50 "measured" blocks are assertions. The assertions are correct, but for other reasons: no encoding exists, the router is not allowlisted, and there is no signing key to steal. These properties are tested on-chain by `test_session_key_cannot_call_a_raw_transfer`, `test_unknown_router_is_rejected`, and `test_stolen_verifier_key_drains_the_signed_baseline`, not by the harness.

**Fix.** Label each harmful family's mechanism in the table (guest decision, ledger, structural), and name the Foundry test that backs each structural row. Say in the text that structural rows are not guest measurements.

### C3. The proved EWMA statistic never decides a trial

**Where.** Sec. V-H ("Why the Risk Function Is Proved") and the contribution list.

**Evidence.** `policy_defaults` in `prover/leash-risk/src/scenarios.rs` sets `max_vol_exposure = 50_000 * ONE` against a $40k portfolio, with sigma measured per observation. Running the CLI gives: in `calm`, sigma is 2.96e-4 for both assets and V = $11.88. In `volatile_buy` (prices swing by up to 80% per step), sigma for WETH is 1.026. After the all-in buy, V = $46,236, still under the $50k limit, and the only deny reason is `concentration`, a cheap check that Solidity repeats anyway. (The calm USDC series also drifts 0.05% per step, which is unrealistic for a stablecoin.) The deny reasons emitted by `leash-risk` were never recorded in the harness output.

**Why it matters.** The paper's justification for a zkVM is the history-dependent statistic. If no trial's outcome depends on it, the evaluation shows a ledger and some cheap caps, not a proved risk function.

**Fix.** Record deny reasons. Calibrate `max_vol_exposure` to the per-observation horizon. Add a family that only the volatility limit denies (a moderate buy, under the $5k static cap and under the 80% concentration cap, in a volatile regime), and add a benign counterpart (the same buy in a calm regime) to show the limit is selective. Add a Foundry test showing that a lying guest (allow bit set, `volExposure` over the limit) is caught by `VolLimit` on-chain.

### C4. "Execute mode" describes something that did not run

**Where.** Sec. VI ("runs unmodified ... inside the SP1 guest", "All results were produced in execute mode"), Sec. VIII ("The evaluation ran in execute mode").

**Evidence.** `prover/cli/src/main.rs` calls `leash_risk::evaluate` natively: "runs the guest logic natively (no proof)". `prover/program` is excluded from the workspace and has never been compiled ("Not built in CI"). In SP1, "execute mode" names a specific operation: run the RISC-V ELF in the SP1 executor without proving. `step_count` in the CLI output counts price points, not cycles.

**Fix.** Build the guest with `cargo prove build`, run it in the SP1 executor, check that its public values are byte-identical to the native CLI's, and report cycle counts by window length. If that cannot be done, replace every "execute mode" with "native execution of the guest crate" and delete "runs unmodified inside the SP1 guest".

### C5. G1 is credited to an off-chain component the adversary controls

**Where.** Abstract ("Transfers can never be executed"), Sec. IV-A ("The transaction builder ... has no encoding for a transfer, so a transfer intent yields no transaction"), Fig. 1.

**Evidence.** The threat model says the adversary may control the prover machine and hold the session key. With the session key, they can sign any UserOp. What stops a transfer is on-chain:

- `SessionKeyValidator._sessionCall` accepts only `account.execute(executor, 0, executeGuarded(...))`.
- `LeashExecutor._swap` hard-codes `recipient: account`, and only approves an allowlisted router for `amountIn`.

The owner can still call `execute` with any target.

**Fix.** Attribute G1 to the validator and executor. Limit the claim to the session-key path ("no session-key operation can move tokens to an address other than the account"). Describe the builder's missing transfer encoding as a convenience, not a security boundary.

### C6. The B3 explanation names the wrong key, and B3 is not PACE

**Where.** Sec. VII-B ("a stolen session key can obtain signatures that the stateless proof would have refused").

**Evidence.** In the `stolen_key` family, what is stolen is the attestation signer's key (`test_stolen_verifier_key_drains_the_signed_baseline`; the older `paper/main.tex` calls the row "Stolen verifier key"). A stolen session key gets nothing from zkLeash. B3 itself is a decision rule in Python that copies the guest's answer except in the two families where it is set to fail. It is not a reimplementation of PACE.

**Fix.** "B3 fails the stolen-key family because whoever holds the attestation key can sign any action; zkLeash has no such key." State once, in the setup, that B1 to B4 are decision rules that stand in for classes of design and are not reimplementations of PACE or Proof-Gated Signing.

### C7. The "drain" is $16 on a $40k portfolio

**Where.** Abstract ("a slow multi-trade drain"), Sec. VII-B and VII-C.

**Evidence.** `max_window_loss = 5 * ONE` ($5) and `_salami` simulates eight legs of 0.1 WETH (about $200), each losing 1% ($2). B4 "fails" by letting eight legs through, a total loss of $16, or 0.04% of the portfolio.

**Fix.** Report the parameters. Replace the yes/no outcome with cumulative loss against number of legs, for a stateless guard and for zkLeash. Show two settings: the toy one, and a realistic one (legs just under the $5k static cap, window cap 1% of the portfolio). The stateless curve grows linearly. The zkLeash curve stops at the cap.

### C8. Anyone can make the history look calm

**Where.** Sec. V-D ("The proof has to cover the entire log, so a prover cannot pick a quiet stretch").

**Evidence.** `PriceHistoryLog.record` is permissionless, calls `updatePriceFeeds` (a no-op for an empty update array), and appends `getPriceUnsafe(priceId)` without checking that `publishTime` advanced. Calling it k times appends k copies of the same price. Each copy contributes a zero return, and the EWMA variance decays by λ per call: σ shrinks by 0.94^(k/2). About 75 calls cut sigma by 90%. The guest does not check timestamps either.

The same function also lets anyone invalidate every outstanding proof by appending a point (proofs must end at the current head). That is a liveness/griefing vector the paper does not mention.

**Fix.** Require `publishTime` to be strictly greater than the previous point's `publishTime` in `record`, and enforce the same in the guest (deny with `bad_price`). Add tests for both. Mention the griefing vector in the limitations, with the mitigations: a short grace window of accepted heads, or a sliding-window index.

---

## Major

### M1. No security analysis

G1 to G3 are stated in Sec. III and never argued. Add a short subsection that maps each goal to the mechanism that enforces it and to the test that exercises it. That subsection should also name the ledger binding, which the paper never mentions: `cumulativePnl`, `peakEquity`, `windowLoss`, `windowStart`, and `tradesInWindow` are committed in the public values and compared with `RiskLedger` (`LedgerMismatch`). That is how state from previous trades enters each proof.

### M2. "Realized loss" is execution loss, not mark-to-market loss

`LeashExecutor` computes `equityBefore` and `equityAfter` at the proven prices, around the swap. The ledger therefore accumulates value given away in execution (slippage, fees, sandwiching, a manipulated pool), not market moves. G3 should say so. This also gives a better framing: the ledger bounds cumulative execution loss, which is exactly what a sandwiching or pool-controlling attacker extracts one leg at a time.

### M3. The attack-success metric is defined by zkLeash's own policy

"An attack counts as successful if value leaves the account in a way the policy prohibits." zkLeash enforces that policy, so a 0.00 rate is partly true by construction. Say this, and say that what the harness measures is which designs enforce a common policy, not resistance to an external notion of harm.

### M4. EWMA methodology

- **Zero initialisation.** With v_0 = 0, the weights on squared returns sum to 1 - λ^n. At `min_history = 8` (seven returns), that is 0.35, so sigma is biased low by a factor of about 0.59. Short histories look calm, which helps the attacker. State it and either seed v_0 with the sample variance or divide by 1 - λ^n.
- **Per-observation horizon.** Returns are taken between consecutive log entries, whatever their spacing. Sigma is per observation, not per unit time, so `max_vol_exposure` only means something relative to the posting cadence. State the cadence assumption.

### M5. The VaR sentence undersells a real property

The text says "No covariance matrix is used, so we claim no diversification benefit." Standard deviation is subadditive: σ(Σ X_i) ≤ Σ σ(X_i) for any correlation structure. So V = Σ E_i σ_i is an upper bound on the portfolio's one-step σ-exposure, and 2.33V bounds the parametric 99% VaR under normal returns. State that, and keep the caveat about normality.

### M6. The gas comparison understates the on-chain alternative

`OnChainEwma.sigma` takes prices as unauthenticated calldata. A real on-chain guard must read the stored history, about 2,100 gas per cold `SLOAD`, which makes the case for proving stronger, not weaker. Measure a storage-reading variant. Also report gas for `executeGuarded` without verification and for `PriceHistoryLog.record`, so a reader can estimate the cost of a proved trade (`executeGuarded` + ~280k).

### M7. Related work is thin

Only PACE and Proof-Gated Signing are discussed. `docs/RELATED_WORK.md` already lists NiyamAI (arXiv 2608.07167), ERC-8354, and CrAIBench. Also relevant, and to be verified before citing: CaMeL (Debenedetti et al., 2025, arXiv:2503.18813), AgentDojo (Debenedetti et al., NeurIPS 2024 D&B, arXiv:2406.13352), InjecAgent (Zhan et al., Findings of ACL 2024, arXiv:2403.02691), ERC-7715 (wallet permissions), and ERC-7265 (circuit breaker). Verified against arXiv and eips.ethereum.org: all of these exist except ERC-7265, which has no EIPs page and is left out.

### M8. Reference problems

- [5] has arXiv ID 2610.00354 and is dated "Sep. 2026". The arXiv listing gives 30 Sep. 2026 as the v1 date, so the date is correct (the ID reflects the announcement month). No change needed.
- [7], [8]: no authors, no year, no URL. IEEE style for EIPs: authors, "ERC-7579: Minimal modular smart accounts," Ethereum Improvement Proposals, no. 7579, year. [Online]. Available: https://eips.ethereum.org/EIPS/eip-7579
- [9], [11]: online sources need "Accessed: Mon. DD, YYYY."
- [3]: check the FC 2026 proceedings details (LNCS volume and pages) once published.

### M9. Fig. 1 hides the trust boundary

It is a straight chain of six boxes. Nothing separates off-chain from on-chain, and the inputs that make the design work (Pyth into the price log, log heads and ledger state into the guest, live Pyth into the executor) are not shown. Redraw it with off-chain and on-chain regions.

---

## Minor and editorial

- **Author block.** Remove the IEEE template ordinals ("1st", "2nd", ...). Fill in the five `[TODO: e-mail]` lines. Mark the corresponding author.
- **Acknowledgment and AI disclosure.** Add an acknowledgment (project guide, department). IEEE requires authors to disclose AI-generated content in the acknowledgments section.
- **Equations.** They are typed text with manual sub/superscripts, not Word equation objects. Eq. (4) has the literal `10d_out` and `10d_in`, and d_in and d_out are never defined (they are token decimals). "1018" must render as 10^18 everywhere.
- **Contribution 4** ("An explicit statement of limits") is not a contribution. Fold it into the paragraph after the list.
- **Abstract.** The last sentence ("the paper states these limitations explicitly") adds nothing. Put the ~280k verification cost next to the gas range so the reader knows what it is compared against. Limit "Transfers can never be executed" to the session-key path (C5).
- **Index terms.** IEEE lists them alphabetically.
- **Execution checks list** (Sec. IV-D) omits the exponent check, the `minHistory` check, the ledger-state match (M1), and the drawdown exemption: a trade that sells into the quote asset without raising V is allowed past the drawdown cap. Reviewers will like that exemption; mention it.
- **Threat model.** Add "can call `record` on the price log" and "can reorder or sandwich the swap within `minOut`" to the adversary, since both are now discussed.
- **Table III.** "Rate" duplicates "Count". Replace with a per-family table.
- **Repository docs.** `README.md` and `paper/SUBMISSION.md` still call `paper/main.tex` the paper source.

---

## Status after the accuracy pass

A second read of `zkLeash_IEEE_paper_v3.docx` against the harness was right on the reporting bugs, and those are fixed in the generator. The figures are embedded again: `revise_docx.py` was dropping image relationships that the new drawings still used. The zkLeash false-block interval is [2.9%, 13.9%], not [0, 13.9%]. The abstract is 244 words and no longer says the 75 structural trials are closed by the session-key interface. Section VIII says those rows are fixed harness booleans, distinguishes the transfer, the unlisted router, and the stolen key, and says B2's structural blocks are the unlisted-router flag. Histories are 32 to 64 prices except the calm rebalance (16 to 64). The $30,000 notional cap is stated, including the 3 all-in denies. The de-risk drawdown is a ledger peak, not the price path. Three of 25 salami trials stop at 20 legs under the loss cap. The cycle rate is 16,609 per additional price on each of two assets. The crash replay discloses the 90% drawdown cap, the 48-hour price age, and the flat $1 USDC. SP1 execution is the calm cycle sweep only. Reference [3] is the arXiv preprint. The PACE "8 of 8" sentence now matches Table 4 of arXiv:2608.17220: eight policy-valid cases, not eight trials of the five-leg drain. Table III stays in the column at 7-point type so nine columns fit in 3.5 inches. The empty single-column section after the references is gone. Pages, which is not Word, lays the file out at 9 pages; the ninth page is the last six references, not a blank sheet. Word is not installed here, so the official page count is still unchecked.

## Status after the October 15 pass

The 0/150 headline below is superseded. The harness is now 250 trials. Measured attack success excludes the 75 structural trials. B5 is a stateless proof plus an $8,000 daily notional cap: it also scores 0/75 on measured attacks, loses about $42 on the salami family against zkLeash's $379, and false-blocks 35/100 benign trials. zkLeash false-blocks 7/100, all fair-turnover days stopped by the 20-trade cap. `bench/crash_replay.py` replays Binance ETH-USDT hourly closes through August 5, 2024: the crash buy is denied by the volatility limit alone, and a risk-reducing sale is allowed. No Groth16 proof and no live model were produced; `bench/model_panel.py` is the panel, and this machine had no Ollama server.

## Status after revision

Code, harness, and `zkLeash_IEEE_paper_v3.docx` were updated against this review. `make test`, `make gas`, `make figures`, `make paper`, and `make sp1-cycles` all completed after the changes. The Foundry suite is 20 tests plus the 128,000-call invariant; Rust is 13 unit tests.

### Code

- **Harness.** `bench/leashbench.py` now draws 225 independent trials (nine families × 25 seeds): price path, volatility regime, trade size, balances, and salami-leg count all depend on the seed. Deny reasons are recorded. Structural families (`direct_transfer`, `illiquid_pool`, `stolen_key`) are labelled and no longer count as guest measurements. McNemar is gone; intervals are exact Clopper-Pearson.
- **Vol family.** `max_vol_exposure` is `40 * ONE` (0.1% of the $40k book) in `policy_defaults` and in `Deploy.s.sol`. New scenarios: `vol_spike_buy` and `volatile_sell`. Foundry: `test_lying_guest_is_caught_by_vol_limit`.
- **Risk-reducing exemption.** Guest and `LeashExecutor` skip the volatility, concentration, and drawdown limits when `tokenOut` is the quote asset and \(V_{\mathrm{post}} \le V_{\mathrm{pre}}\). Notional, slippage, and the loss ledger still apply. Tests: `selling_into_quote_over_budget_is_allowed_and_buying_is_not`, `risk_reducing_exemption_needs_the_quote_asset_as_output`, `test_derisk_over_vol_budget_is_allowed`. Without the exemption, zkLeash, B3, and B4 would have false-blocked all 25 de-risking sales; with it they pass them.
- **Price-log monotonicity.** `PriceHistoryLog.record` reverts `StalePrice` if `publishTime` does not increase. The guest denies `non_increasing_time`. Tests: `repeated_publish_time_is_denied`, `test_price_log_refuses_a_repeated_publish_time`.
- **Gas.** `OnChainEwma` has a storage-reading variant. `test_gas_trade_path_samples` and `bench/gas_samples.py` collect calldata vs storage EWMA, `executeGuarded`, verifier stand-in, and `record`.
- **SP1.** `prover/program` upgraded to `sp1-zkvm` 6.9.0 (the May 2026 toolchain emits riscv64; v5 rejected it). `prover/exec` runs the ELF in the SP1 v6 executor (`sp1-sdk` 6.9.0, `blocking` feature) and checks public values against native `evaluate`. Building the guest also needed `use alloc::vec;` in `scenarios.rs` (C4: the crate had never been compiled for SP1).
- **Salami.** Legs and slippage are parameterized. `bench/plot_results.py` writes `bench/results/salami_curve.png`.

### New results

Harness, 150 harmful / 75 benign:

| System | Attack success | False blocks |
| --- | --- | --- |
| B0 unguarded | 150/150 | 0/75 |
| B1 keyword | 128/150 | 0/75 |
| B2 static cap | 50/150 | 25/75 (all de-risking sales) |
| B3 signed | 50/150 | 0/75 |
| B4 stateless | 25/150 | 0/75 |
| zkLeash | 0/150 (CI [0, 0.0243]) | 0/75 (CI [0, 0.048]) |

Guest-decided harmful trials: 0/75 for zkLeash. `vol_spike` is denied by the volatility limit only (25/25). Salami: B2/B4 lose a mean of $827 (max $1,419); zkLeash runs 8–20 legs and stops at $399 against a $400 cap.

EWMA gas, one asset, from storage: 36,116 / 114,694 / 219,469 / 429,031 at 8 / 32 / 64 / 128 points. From calldata: 18,873 to 182,510. 280k crossover: 82 points (storage) / 201 (calldata). `executeGuarded`: 331,518 first / 260,218 next; stand-in verifier 5,332; about 535k with Groth16. `record`: 95,732.

SP1 executor cycles (two assets, native public values identical on every run): 334,624 (8 points/asset) … 4,453,756 (256). About 8,305 cycles per additional price.

### Paper (`zkLeash_IEEE_paper_v3.docx`)

Regenerated by `paper/tools/revise_docx.py` from the original docx plus `bench/results/{summary,gas,sp1_cycles}.json`. About 4,988 paragraph words, two figures, three tables (plus the author table). Estimated ~6.5 of 8 pages; not rendered in Word.

| Item | What changed |
| --- | --- |
| C1 | 225 randomized trials; Clopper-Pearson; McNemar dropped. |
| C2 | Table III has a Mech. column (S / G / G+L) and names the Foundry tests for structural rows. |
| C3 | `vol_spike` family; deny reasons; `max_vol_exposure` = 40. |
| C4 | Native vs SP1-execute wording; cycle counts; byte-identical public values. |
| C5 | G1 attributed to the validator/executor; session-key path only. |
| C6 | B3 fails because the attestation key is stolen; B1–B4 are stand-ins, not PACE. |
| C7 | Salami parameters and Fig. 2 (cumulative loss vs legs). |
| C8 | Strictly increasing `publishTime`; liveness/griefing named in the discussion. |
| M1 | New Sec. VI Security Analysis. |
| M2 | “Execution loss” throughout. |
| M3 | Attack-success defined as a common-policy comparison. |
| M4 | Zero-init bias \(\sqrt{1-\lambda^m}\) and cadence stated. |
| M5 | Subadditivity of \(V\); 2.33\(V\) bounds parametric VaR99. |
| M6 | Storage vs calldata gas; trade-path gas. |
| M7 | InjecAgent, AgentDojo, CaMeL, NiyamAI, ERC-8354, ERC-7715 added. ERC-7265 dropped (no EIP). |
| M8 | [5] date confirmed (30 Sep 2026). EIP refs completed. “Accessed: Oct. 11, 2026” on online sources. |
| M9 | Fig. 1 redrawn with off-chain / on-chain lanes. |
| Minor | Author ordinals removed; equations in OMML; 3 contributions; index terms alphabetical; exemption listed; 17 references. |

`README.md`, `docs/GUIDE.md`, `docs/PROJECT_REPORT.md`, `docs/PUBLIC_VALUES.md`, `docs/VIVA.md`, `docs/SYNOPSIS.md`, `docs/RISK_MODEL.md`, `docs/THREAT_MODEL.md`, and `paper/SUBMISSION.md` now match the new numbers and wording.

### Remaining author TODOs

- Five author e-mails and the corresponding-author mark (highlighted in the docx).
- Guide name in the acknowledgment (highlighted).
- Confirm the IEEE AI-use disclosure sentence.
- If Patlan et al. appear in the FC proceedings, replace arXiv:2503.16248 with the LNCS volume and pages.
- Open the docx in Word (not Pages) and check page count and equation rendering.
