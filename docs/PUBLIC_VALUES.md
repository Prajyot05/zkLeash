# Public values and hashes

The guest output is `abi.encode` of a fully static tuple. Both sides use the same word order. The Rust encoder is `prover/leash-risk/src/encode.rs`. The Solidity decoder is `LeashTypes.PublicValues`.

| Words | Field | Type |
| --- | --- | --- |
| 0 | actionHash | bytes32 |
| 1 | policyCommitment | bytes32 |
| 2 | assetCount | uint8 |
| 3 | expiry | uint64 |
| 4 | decision | uint8 (1 = allow, 0 = deny) |
| 5 | cumulativePnl | int256 |
| 6 | peakEquity | uint256 |
| 7 | windowLoss | uint256 |
| 8 | windowStart | uint64 |
| 9 | tradesInWindow | uint32 |
| 10 | volExposure | uint256 |
| 11 | var99 | uint256 |
| 12–19 | headStart | bytes32[8] |
| 20–27 | headEnd | bytes32[8] |
| 28–35 | provenPrices | int64[8] |
| 36–43 | sigmas | uint256[8] |
| 44–51 | balances | uint256[8] |

52 words, 1664 bytes. Unused asset slots are zero.

## Action hash

```text
keccak256(abi.encode(
  chainId, account, router, tokenIn, tokenOut, fee, amountIn, deadline, nonce
))
```

The executor recomputes this from the swap it is about to run and from its own nonce. A mutated router, amount, or token does not match.

## Policy commitment

```text
keccak256(abi.encode(
  maxVolExposure, maxConcentrationBps, maxDrawdownBps, maxNotional,
  maxSlippageBps, maxWindowLoss, windowSeconds, maxTradesPerWindow,
  minHistory, maxPriceDeviationBps, maxPriceAge, quoteToken
))
```

## Price head

```text
keccak256(abi.encodePacked(prevHead, int64 price, uint64 conf, int32 expo, uint64 publishTime))
```

`headStart[i]` is the head after the first point in the window. `headEnd[i]` is the head after the last. The executor requires those to equal `heads[priceId][0]` and `heads[priceId][length-1]`, so the proof has to cover the whole log. Appending a point invalidates outstanding proofs. That is fail-closed.

## Intent schema

The model emits one of `swap`, `transfer`, or `hold` (see `agent/zkleash_agent/schema.py`). A transfer has no encoding in this ABI, so it cannot be proved and the executor will not run it.
