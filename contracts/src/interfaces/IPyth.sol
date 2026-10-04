// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @notice The slice of the Pyth pull-oracle interface this project actually calls.
interface IPyth {
    struct Price {
        int64 price;
        uint64 conf;
        int32 expo;
        uint256 publishTime;
    }

    function getUpdateFee(bytes[] calldata updateData) external view returns (uint256);

    function updatePriceFeeds(bytes[] calldata updateData) external payable;

    function getPriceUnsafe(bytes32 id) external view returns (Price memory price);

    function getPriceNoOlderThan(bytes32 id, uint256 age) external view returns (Price memory price);
}
