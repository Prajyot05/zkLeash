// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @notice Baseline B2: allowlisted targets and a per-transaction notional cap.
/// No history, no proof, no rolling loss.
contract StaticSessionGuard {
    address public owner;
    uint256 public maxNotional;
    mapping(address => bool) public allowed;

    error NotAllowed();
    error TooLarge();

    constructor(address owner_, uint256 maxNotional_) {
        owner = owner_;
        maxNotional = maxNotional_;
    }

    function setAllowed(address target, bool ok) external {
        require(msg.sender == owner, "owner");
        allowed[target] = ok;
    }

    function execute(address target, uint256 value, bytes calldata data, uint256 notional) external {
        if (!allowed[target]) revert NotAllowed();
        if (notional > maxNotional || value > maxNotional) revert TooLarge();
        (bool ok,) = target.call{value: value}(data);
        require(ok, "call");
    }
}
