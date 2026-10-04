// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @notice Baseline B3: a trusted off-chain signer, in the style of PACE's
/// Policy Decision Record. If that key is stolen, the guard accepts the theft.
contract SignedAttestationGuard {
    address public immutable signer;
    mapping(bytes32 => bool) public used;

    error BadSigner();
    error Replay();

    constructor(address signer_) {
        signer = signer_;
    }

    function execute(address target, uint256 value, bytes calldata data, uint256 nonce, bytes calldata signature)
        external
    {
        bytes32 digest = keccak256(abi.encode(block.chainid, msg.sender, target, value, keccak256(data), nonce));
        if (used[digest]) revert Replay();
        if (_recover(digest, signature) != signer) revert BadSigner();
        used[digest] = true;
        (bool ok,) = target.call{value: value}(data);
        require(ok, "call");
    }

    function _recover(bytes32 hash, bytes calldata signature) internal pure returns (address) {
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := calldataload(signature.offset)
            s := calldataload(add(signature.offset, 32))
            v := byte(0, calldataload(add(signature.offset, 64)))
        }
        if (v < 27) v += 27;
        return ecrecover(hash, v, r, s);
    }
}
