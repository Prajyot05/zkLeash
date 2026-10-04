// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {LeashTypes} from "./LeashTypes.sol";

/// @notice Hash helpers. Byte layout is frozen in `docs/PUBLIC_VALUES.md` and
/// duplicated by `prover/leash-risk/src/encode.rs`.
library Commitments {
    function actionHash(
        uint256 chainId,
        address account,
        address router,
        address tokenIn,
        address tokenOut,
        uint256 fee,
        uint256 amountIn,
        uint256 deadline,
        uint256 nonce
    ) internal pure returns (bytes32) {
        return keccak256(abi.encode(chainId, account, router, tokenIn, tokenOut, fee, amountIn, deadline, nonce));
    }

    function policyCommitment(LeashTypes.Policy memory policy) internal pure returns (bytes32) {
        return keccak256(
            abi.encode(
                policy.maxVolExposure,
                policy.maxConcentrationBps,
                policy.maxDrawdownBps,
                policy.maxNotional,
                policy.maxSlippageBps,
                policy.maxWindowLoss,
                policy.windowSeconds,
                policy.maxTradesPerWindow,
                policy.minHistory,
                policy.maxPriceDeviationBps,
                policy.maxPriceAge,
                policy.quoteToken
            )
        );
    }

    function nextHead(bytes32 prev, int64 price, uint64 conf, int32 expo, uint64 publishTime)
        internal
        pure
        returns (bytes32)
    {
        return keccak256(abi.encodePacked(prev, price, conf, expo, publishTime));
    }
}
