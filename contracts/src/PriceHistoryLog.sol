// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IPyth} from "./interfaces/IPyth.sol";
import {Commitments} from "./lib/Commitments.sol";

/// @notice Append-only hash chain of Pyth-verified prices.
/// Anyone may call `record`. Pyth checks the update, so the caller is not trusted.
/// A missed update only stops new trades (fail closed). It cannot fake a calm history:
/// each point must carry a newer Pyth publish time than the last, so re-recording the
/// same price to add zero returns is refused.
contract PriceHistoryLog {
    IPyth public immutable pyth;

    mapping(bytes32 priceId => uint256) public lengthOf;
    mapping(bytes32 priceId => mapping(uint256 index => bytes32 head)) public heads;
    mapping(bytes32 priceId => mapping(uint256 index => int64 price)) public prices;
    mapping(bytes32 priceId => uint64) public lastPublishTime;

    error StalePrice();

    event PriceRecorded(bytes32 indexed priceId, uint256 index, bytes32 head, int64 price, uint64 publishTime);

    constructor(IPyth pyth_) {
        pyth = pyth_;
    }

    function record(bytes[] calldata updates, bytes32 priceId) external payable {
        uint256 fee = pyth.getUpdateFee(updates);
        pyth.updatePriceFeeds{value: fee}(updates);
        IPyth.Price memory px = pyth.getPriceUnsafe(priceId);
        uint64 publishTime = uint64(px.publishTime);
        uint256 n = lengthOf[priceId];
        if (n != 0 && publishTime <= lastPublishTime[priceId]) revert StalePrice();
        bytes32 prev = n == 0 ? bytes32(0) : heads[priceId][n - 1];
        bytes32 next = Commitments.nextHead(prev, px.price, px.conf, px.expo, publishTime);
        heads[priceId][n] = next;
        prices[priceId][n] = px.price;
        lengthOf[priceId] = n + 1;
        lastPublishTime[priceId] = publishTime;
        emit PriceRecorded(priceId, n, next, px.price, publishTime);
    }
}
