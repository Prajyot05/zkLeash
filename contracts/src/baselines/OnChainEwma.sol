// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {RiskMath} from "../lib/RiskMath.sol";

/// @notice The same EWMA the guest proves, computed in Solidity.
/// Used only for the gas-crossover measurement, not on the trade path.
contract OnChainEwma {
    /// @dev Same layout as `PriceHistoryLog.prices`: one slot per point.
    mapping(uint256 index => int64 price) public stored;
    uint256 public storedLength;

    /// Prices passed as calldata. Nothing authenticates them, so this is a lower bound.
    function sigma(int64[] calldata prices) external pure returns (uint256) {
        int64[] memory copy = new int64[](prices.length);
        for (uint256 i = 0; i < prices.length; ++i) copy[i] = prices[i];
        return RiskMath.ewmaSigma(copy);
    }

    function load(int64[] calldata prices) external {
        for (uint256 i = 0; i < prices.length; ++i) stored[i] = prices[i];
        storedLength = prices.length;
    }

    /// What an on-chain guard pays when it reads the logged history itself.
    function sigmaFromStorage() external view returns (uint256) {
        uint256 n = storedLength;
        int64[] memory copy = new int64[](n);
        for (uint256 i = 0; i < n; ++i) copy[i] = stored[i];
        return RiskMath.ewmaSigma(copy);
    }
}
