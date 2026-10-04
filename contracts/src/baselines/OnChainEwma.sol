// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {RiskMath} from "../lib/RiskMath.sol";

/// @notice The same EWMA the guest proves, computed in Solidity.
/// Used only for the gas-crossover measurement (RQ4), not on the trade path.
contract OnChainEwma {
    function sigma(int64[] calldata prices) external pure returns (uint256) {
        int64[] memory copy = new int64[](prices.length);
        for (uint256 i = 0; i < prices.length; ++i) copy[i] = prices[i];
        return RiskMath.ewmaSigma(copy);
    }
}
