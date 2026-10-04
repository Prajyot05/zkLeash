// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {RiskLedger} from "../src/RiskLedger.sol";

/// @notice Handler the fuzzer drives. Every trade either lands inside the cap
/// or reverts, and a revert rolls the ledger back.
contract LedgerHandler is Test {
    RiskLedger public ledger;
    address public constant ACCOUNT = address(0xA11CE);
    uint256 public constant CAP = 1_000 ether;
    uint64 public nowTs = 1_700_000_000;

    constructor(RiskLedger ledger_) {
        ledger = ledger_;
    }

    function trade(uint96 loss) external {
        loss = uint96(bound(loss, 0, CAP));
        try ledger.applyTrade(ACCOUNT, -int256(uint256(loss)), 0, loss, nowTs, 1 days, CAP, 50) {} catch {}
        nowTs += 60;
    }
}

contract LedgerInvariantTest is Test {
    RiskLedger ledger;
    LedgerHandler handler;

    function setUp() public {
        ledger = new RiskLedger();
        handler = new LedgerHandler(ledger);
        ledger.setExecutor(address(handler));
        targetContract(address(handler));
    }

    function invariant_windowLossNeverExceedsCap() public view {
        assertLe(ledger.stateOf(handler.ACCOUNT()).windowLoss, handler.CAP());
    }
}
