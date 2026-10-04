// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {ISwapRouter} from "../interfaces/ISwapRouter.sol";
import {MockERC20} from "./MockERC20.sol";

/// @notice Uniswap V3 `exactInputSingle` shaped mock. `payout` is the amount of
/// `tokenOut` minted to the recipient. Tests set it to the fair amount or to `minOut`.
contract MockRouter is ISwapRouter {
    uint256 public payout;

    function setPayout(uint256 payout_) external {
        payout = payout_;
    }

    function exactInputSingle(ExactInputSingleParams calldata params) external returns (uint256 amountOut) {
        MockERC20(params.tokenIn).transferFrom(msg.sender, address(this), params.amountIn);
        amountOut = payout;
        require(amountOut >= params.amountOutMinimum, "router minOut");
        MockERC20(params.tokenOut).mint(params.recipient, amountOut);
    }
}
