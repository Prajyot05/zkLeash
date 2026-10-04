// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {PackedUserOperation} from "./interfaces/IERC7579.sol";

interface IAccountValidator {
    function validateUserOp(PackedUserOperation calldata userOp, bytes32 userOpHash) external view returns (uint256);
}

/// @notice Minimal ERC-4337 account that installs one validator and one executor.
/// A production deployment would be Kernel or Safe7579; this account implements the
/// same call path those accounts use, so the modules stay portable.
contract LeashAccount {
    address public owner;
    address public entryPoint;
    address public sessionKey;
    address public validator;
    address public executor;
    uint256 public nonce;

    error NotEntryPoint();
    error NotOwner();
    error NotExecutor();
    error CallFailed(bytes data);

    event ModulesInstalled(address validator, address executor);

    constructor(address owner_, address entryPoint_) {
        owner = owner_;
        entryPoint = entryPoint_;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    function installModules(address validator_, address executor_) external onlyOwner {
        validator = validator_;
        executor = executor_;
        emit ModulesInstalled(validator_, executor_);
    }

    function setSessionKey(address sessionKey_) external onlyOwner {
        sessionKey = sessionKey_;
    }

    function setOwner(address next) external onlyOwner {
        owner = next;
    }

    function validateUserOp(PackedUserOperation calldata userOp, bytes32 userOpHash, uint256 missingAccountFunds)
        external
        returns (uint256 validationData)
    {
        if (msg.sender != entryPoint) revert NotEntryPoint();
        bytes32 expected = keccak256(abi.encode(block.chainid, userOp.sender, userOp.nonce, keccak256(userOp.callData)));
        require(userOpHash == expected, "hash");
        require(userOp.nonce == nonce, "nonce");
        validationData = IAccountValidator(validator).validateUserOp(userOp, userOpHash);
        if (validationData == 0) nonce = userOp.nonce + 1;
        if (missingAccountFunds > 0) {
            (bool ok,) = payable(msg.sender).call{value: missingAccountFunds}("");
            require(ok, "prefund");
        }
    }

    /// @dev EntryPoint calls this. The owner may also call it as the recovery path.
    function execute(address target, uint256 value, bytes calldata data) external returns (bytes memory) {
        if (msg.sender != entryPoint && msg.sender != owner) revert NotEntryPoint();
        return _call(target, value, data);
    }

    function executeFromExecutor(address target, uint256 value, bytes calldata data) external returns (bytes memory) {
        if (msg.sender != executor) revert NotExecutor();
        require(target != address(this), "self");
        return _call(target, value, data);
    }

    function _call(address target, uint256 value, bytes calldata data) internal returns (bytes memory) {
        (bool ok, bytes memory ret) = target.call{value: value}(data);
        if (!ok) revert CallFailed(ret);
        return ret;
    }

    receive() external payable {}
}
