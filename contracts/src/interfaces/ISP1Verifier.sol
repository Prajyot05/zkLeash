// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @notice Same shape as Succinct's `ISP1Verifier.verifyProof`.
interface ISP1Verifier {
    function verifyProof(bytes32 programVKey, bytes calldata publicValues, bytes calldata proofBytes) external view;
}
