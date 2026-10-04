// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {ISP1Verifier} from "../interfaces/ISP1Verifier.sol";

/// @notice Stand-in for Succinct's `SP1MockVerifier`. Accepts every proof.
/// Useful for local integration. It does NOT bind `publicValues`, so security
/// tests that need that binding use `SP1HonestVerifier` instead.
contract SP1MockVerifier is ISP1Verifier {
    function verifyProof(bytes32, bytes calldata, bytes calldata) external pure {}
}
