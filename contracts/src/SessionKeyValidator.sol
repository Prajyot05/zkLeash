// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IERC7579Module, MODULE_TYPE_VALIDATOR, PackedUserOperation} from "./interfaces/IERC7579.sol";
import {LeashAccount} from "./LeashAccount.sol";
import {LeashExecutor} from "./LeashExecutor.sol";

/// @notice ERC-7579 validator. The owner may do anything. The session key may
/// only call `executor.executeGuarded`. It cannot install or remove modules.
contract SessionKeyValidator is IERC7579Module {
    uint256 internal constant SIG_VALIDATION_FAILED = 1;

    function onInstall(bytes calldata) external {}

    function onUninstall(bytes calldata) external {}

    function isModuleType(uint256 moduleTypeId) external pure returns (bool) {
        return moduleTypeId == MODULE_TYPE_VALIDATOR;
    }

    function validateUserOp(PackedUserOperation calldata userOp, bytes32 userOpHash) external view returns (uint256) {
        LeashAccount account = LeashAccount(payable(msg.sender));
        address signer = _recover(userOpHash, userOp.signature);
        if (signer == account.owner()) return 0;
        if (signer != account.sessionKey()) return SIG_VALIDATION_FAILED;
        if (!_sessionCall(userOp.callData, account.executor())) return SIG_VALIDATION_FAILED;
        return 0;
    }

    function _sessionCall(bytes calldata callData, address executor) internal pure returns (bool) {
        if (callData.length < 4) return false;
        if (bytes4(callData[:4]) != LeashAccount.execute.selector) return false;
        (address target, uint256 value, bytes memory inner) = abi.decode(callData[4:], (address, uint256, bytes));
        if (target != executor || value != 0) return false;
        if (inner.length < 4) return false;
        return bytes4(inner) == LeashExecutor.executeGuarded.selector;
    }

    function _recover(bytes32 hash, bytes calldata signature) internal pure returns (address) {
        if (signature.length != 65) return address(0);
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := calldataload(signature.offset)
            s := calldataload(add(signature.offset, 32))
            v := byte(0, calldataload(add(signature.offset, 64)))
        }
        if (v < 27) v += 27;
        if (v != 27 && v != 28) return address(0);
        return ecrecover(hash, v, r, s);
    }
}
