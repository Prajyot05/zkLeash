// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {PackedUserOperation} from "../interfaces/IERC7579.sol";
import {LeashAccount} from "../LeashAccount.sol";

/// @notice Just enough of an EntryPoint to exercise validateUserOp then execute.
contract MockEntryPoint {
    function handleOp(PackedUserOperation calldata op) external payable {
        bytes32 userOpHash = keccak256(abi.encode(block.chainid, op.sender, op.nonce, keccak256(op.callData)));
        uint256 vd = LeashAccount(payable(op.sender)).validateUserOp(op, userOpHash, 0);
        require(vd == 0, "validation");
        (bool ok, bytes memory ret) = op.sender.call(op.callData);
        if (!ok) {
            assembly {
                revert(add(ret, 32), mload(ret))
            }
        }
    }

    function hashOp(PackedUserOperation calldata op) external view returns (bytes32) {
        return keccak256(abi.encode(block.chainid, op.sender, op.nonce, keccak256(op.callData)));
    }
}
