// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IPyth} from "../interfaces/IPyth.sol";

contract MockPyth is IPyth {
    mapping(bytes32 => Price) internal _prices;

    function setPrice(bytes32 id, int64 price, uint64 conf, int32 expo, uint256 publishTime) external {
        _prices[id] = Price({price: price, conf: conf, expo: expo, publishTime: publishTime});
    }

    function getUpdateFee(bytes[] calldata) external pure returns (uint256) {
        return 0;
    }

    function updatePriceFeeds(bytes[] calldata) external payable {}

    function getPriceUnsafe(bytes32 id) external view returns (Price memory price) {
        price = _prices[id];
        require(price.price > 0, "missing");
    }

    function getPriceNoOlderThan(bytes32 id, uint256 age) external view returns (Price memory price) {
        price = _prices[id];
        require(price.price > 0, "missing");
        require(price.publishTime + age >= block.timestamp, "stale");
    }
}
