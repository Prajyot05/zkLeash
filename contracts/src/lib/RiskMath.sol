// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @title RiskMath
/// @notice Integer helpers shared by the executor and the on-chain EWMA baseline.
/// Truncation matches the Rust guest: division rounds toward zero.
library RiskMath {
    uint256 internal constant ONE = 1e18;
    uint256 internal constant LAMBDA = 940_000_000_000_000_000;

    function price1e18(int64 price, int32 expo) internal pure returns (uint256) {
        require(price > 0, "price");
        require(expo >= -18 && expo <= 18, "expo");
        return uint256(uint64(price)) * (10 ** uint256(uint32(18 + expo)));
    }

    function exposure(uint256 balance, uint256 px, uint8 decimals) internal pure returns (uint256) {
        return balance * px / (10 ** uint256(decimals));
    }

    /// @dev `amountIn * priceIn * 10^decOut / (priceOut * 10^decIn)`.
    function fairOut(uint256 amountIn, uint8 decIn, uint256 priceIn, uint8 decOut, uint256 priceOut)
        internal
        pure
        returns (uint256)
    {
        require(priceOut != 0, "priceOut");
        return amountIn * priceIn * (10 ** uint256(decOut)) / (priceOut * (10 ** uint256(decIn)));
    }

    function minOut(uint256 fair, uint256 slippageBps) internal pure returns (uint256) {
        require(slippageBps < 10_000, "slippage");
        return fair * (10_000 - slippageBps) / 10_000;
    }

    /// @dev RiskMetrics EWMA volatility, lambda = 0.94, result scaled by 1e18.
    function ewmaSigma(int64[] memory prices) internal pure returns (uint256 sigma) {
        require(prices.length >= 2, "len");
        uint256 variance;
        for (uint256 i = 1; i < prices.length; ++i) {
            require(prices[i] > 0 && prices[i - 1] > 0, "price");
            uint256 r = _absReturn(prices[i - 1], prices[i]);
            uint256 r2 = r * r / ONE;
            variance = (LAMBDA * variance + (ONE - LAMBDA) * r2) / ONE;
        }
        sigma = _isqrt(variance * ONE);
    }

    function _absReturn(int64 prev, int64 next) private pure returns (uint256) {
        int256 delta = int256(next) - int256(prev);
        if (delta < 0) delta = -delta;
        return uint256(delta) * ONE / uint256(uint64(prev));
    }

    function _isqrt(uint256 n) private pure returns (uint256) {
        if (n == 0) return 0;
        uint256 x = n;
        uint256 y = x / 2 + 1;
        while (y < x) {
            x = y;
            y = (x + n / x) / 2;
        }
        return x;
    }
}
