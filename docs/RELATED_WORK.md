# Related work

The claim is not "a ZK proof can gate an agent". That sentence is already published. The claim is the combination in the table: no trusted signer, authenticated history, a history-dependent risk statistic, and a stateful ledger, shipped as 4337/7579 modules.

| System | Removes the trusted signer | Authenticates the inputs the check uses | History-dependent risk | Stops multi-trade drains | Native 4337/7579 module |
| --- | --- | --- | --- | --- | --- |
| PACE (arXiv 2608.17220, Aug 2026) | No. Signed policy decision | Simulation, trusted verifier | No. Per-transaction fields | No. Authors list this as future work | Listed as future work |
| Proof-Gated Signing (arXiv 2610.00354, Sep 2026) | No. Guard holds the key | Trusted static oracle band | No. Value and permission checks | Bounded only by a flat session budget | Listed as future work |
| NiyamAI (arXiv 2608.07167, Aug 2026) | Yes, EZKL proof of a classifier | No | No economic history | No | No |
| ERC-8354 confidential verdicts | Yes, if the backend is a zkVM | Only the action commitment | No. Stateless allow/deny | No | A guard interface, SP1 program is a skeleton |
| Coinbase Agentic Wallets, Lit Vincent | No. Operator or threshold network | Their own infrastructure | Spend caps | Caps, off-chain | No |
| zkLeash (this project) | Yes | Pyth pull for the live price, hash-chained log for history | EWMA volatility over that log | Ledger plus post-trade loss | Validator plus executor |

Attack papers used as the threat, not as systems to extend:

- Patlan et al., "Real AI Agents with Fake Memories" (arXiv:2503.16248) and CrAIBench. The arXiv record had no proceedings entry when checked on Oct 15, 2026. Context and memory injection against Web3 agents. Our harness is smaller and scripted; it is not a re-implementation of CrAIBench, and the paper should not claim that it is.
- Perez and Ribeiro (2022), Greshake et al. (2023): direct and indirect prompt injection.

Other context, not competing systems:

- ERC-4337, ERC-7562 (why the proof cannot be checked inside `validateUserOp`), ERC-7579, ERC-7780.
- SP1 and `sp1-contract-call` (the latter is future work for proving pool state).
- Pyth pull oracles.
- RiskMetrics EWMA (longer lambda literature is cited in the paper).

Search to re-run before submission: arXiv cs.CR, queries pairing "agent" with "zk", "policy", or "DeFi". The field moved between the first draft of this idea and this plan. It will move again.
