// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @notice Shared structs. Field order of `PublicValues` is the ABI of the SP1 guest output.
library LeashTypes {
    struct Policy {
        uint256 maxVolExposure;
        uint256 maxConcentrationBps;
        uint256 maxDrawdownBps;
        uint256 maxNotional;
        uint256 maxSlippageBps;
        uint256 maxWindowLoss;
        uint64 windowSeconds;
        uint32 maxTradesPerWindow;
        uint32 minHistory;
        uint32 maxPriceDeviationBps;
        uint64 maxPriceAge;
        address quoteToken;
    }

    struct SwapAction {
        address router;
        address tokenIn;
        address tokenOut;
        uint24 fee;
        uint256 amountIn;
        uint64 deadline;
    }

    /// @dev 52 static words. See docs/PUBLIC_VALUES.md.
    struct PublicValues {
        bytes32 actionHash;
        bytes32 policyCommitment;
        uint8 assetCount;
        uint64 expiry;
        uint8 decision;
        int256 cumulativePnl;
        uint256 peakEquity;
        uint256 windowLoss;
        uint64 windowStart;
        uint32 tradesInWindow;
        uint256 volExposure;
        uint256 var99;
        bytes32[8] headStart;
        bytes32[8] headEnd;
        int64[8] provenPrices;
        uint256[8] sigmas;
        uint256[8] balances;
    }

    struct Asset {
        address token;
        bytes32 priceId;
        uint8 decimals;
        int32 expo;
        bool allowed;
    }
}
