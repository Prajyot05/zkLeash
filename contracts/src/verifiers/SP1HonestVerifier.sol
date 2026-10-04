// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {ISP1Verifier} from "../interfaces/ISP1Verifier.sol";

/// @notice Local stand-in for a sound verifier. The proof bytes must be
/// `bytes32(keccak256(abi.encode(programVKey, keccak256(publicValues))))`.
/// A real deployment uses the SP1 Groth16 verifier gateway; this contract
/// exists so tests can show that swapping public values invalidates the proof
/// without a proving key.
contract SP1HonestVerifier is ISP1Verifier {
    error BadProof();

    function verifyProof(bytes32 programVKey, bytes calldata publicValues, bytes calldata proofBytes) external pure {
        bytes32 digest = keccak256(abi.encode(programVKey, keccak256(publicValues)));
        if (proofBytes.length != 32 || bytes32(proofBytes) != digest) revert BadProof();
    }

    function prove(bytes32 programVKey, bytes memory publicValues) external pure returns (bytes memory) {
        return abi.encodePacked(keccak256(abi.encode(programVKey, keccak256(publicValues))));
    }
}
