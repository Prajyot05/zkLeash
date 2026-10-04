# Risk model

All arithmetic is fixed-point with scale `1e18`. There are no floats in the guest. Prices are Pyth `int64` values with a per-feed exponent, normally `-8`.

## Price and exposure

```text
price1e18 = price * 10^(18 + expo)
exposure  = balance * price1e18 / 10^decimals
```

## Return and EWMA volatility

Lambda is `0.94`.

```text
r        = (p_t - p_{t-1}) * 1e18 / p_{t-1}
variance = lambda * variance + (1 - lambda) * (r^2 / 1e18)     # all in 1e18
sigma    = isqrt(variance * 1e18)
```

The worked example `[1000, 1100, 1210]` gives `sigma = 34117444218463961` (about `0.0341`). The Solidity port in `RiskMath.ewmaSigma` returns the same integer, and a NumPy float reference stays within 1% on a longer path (`prover/reference/test_ewma_numpy.py`).

History shorter than `minHistory` (8 in the demo policy) is a deny.

## Volatility-scaled exposure, reported as a VaR limit

```text
volExposure = sum_i exposure_i * sigma_i / 1e18
var99       = volExposure * 2.33
```

The policy stores `maxVolExposure`. Multiplying by `2.33` is one extra multiplication, so the paper can call the same limit a parametric 99% VaR without a second algorithm. The guest and the executor both compute `volExposure` from the committed sigmas and the post-trade balances. They must match.

Post-trade balances use the fair oracle amount, not `minOut`:

```text
fairOut = amountIn * priceIn * 10^decOut / (priceOut * 10^decIn)
```

`minOut = fairOut * (10000 - slippageBps) / 10000` is enforced on the tokens that actually arrive. Using the fair amount for risk avoids understating the exposure of an asset the trader is buying.

## On-chain, not in the guest

These are cheap, so the executor does them in Solidity. A bug in the guest's comparison cannot waive them.

- Per-asset concentration of non-quote exposure, in basis points of portfolio value. The quote token is exempt, so a risk-off move into USDC is not blocked for being "100% concentrated".
- Per-trade notional.
- Rolling drawdown against the ledger peak. Past the limit, the only allowed swap is into the quote token, and it must not increase volatility-scaled exposure.
- Rolling realized loss and trade count, updated after the swap from the oracle-valued equity change.

## What was left out on purpose

Historical CVaR needs a sort. Uniswap v3 tick math needs the pool's tick bitmap. Both are implemented only as notes and, for CVaR, as a tested helper that the guest does not call. See `docs/FUTURE_SCOPE.md`.
