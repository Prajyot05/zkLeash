// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

/// @notice Per-account rolling loss and drawdown peak. Only the executor may write.
contract RiskLedger {
    struct State {
        int256 cumulativePnl;
        uint256 peakEquity;
        uint256 windowLoss;
        uint64 windowStart;
        uint32 tradesInWindow;
    }

    address public executor;
    mapping(address account => State) public states;

    error NotExecutor();
    error WindowLossExceeded();
    error TradeRateExceeded();

    event LedgerUpdated(address indexed account, int256 cumulativePnl, uint256 windowLoss, uint256 peakEquity);

    function setExecutor(address executor_) external {
        require(executor == address(0) || msg.sender == executor, "executor");
        executor = executor_;
    }

    function stateOf(address account) external view returns (State memory) {
        return states[account];
    }

    /// @dev Applies one realized PnL. Resets the window if it has elapsed, then
    /// reverts if the cap would be crossed. The executor calls this after the swap,
    /// so a revert rolls the swap back too.
    function applyTrade(
        address account,
        int256 pnl,
        uint256 equityAfter,
        uint256 loss,
        uint64 nowTs,
        uint64 windowSeconds,
        uint256 maxWindowLoss,
        uint32 maxTrades
    ) external {
        if (msg.sender != executor) revert NotExecutor();
        State storage s = states[account];
        if (s.windowStart != 0 && nowTs > s.windowStart + windowSeconds) {
            s.windowLoss = 0;
            s.tradesInWindow = 0;
            s.windowStart = nowTs;
        }
        if (s.windowStart == 0) s.windowStart = nowTs;
        s.cumulativePnl += pnl;
        if (equityAfter > s.peakEquity) s.peakEquity = equityAfter;
        s.windowLoss += loss;
        if (s.windowLoss > maxWindowLoss) revert WindowLossExceeded();
        s.tradesInWindow += 1;
        if (s.tradesInWindow > maxTrades) revert TradeRateExceeded();
        emit LedgerUpdated(account, s.cumulativePnl, s.windowLoss, s.peakEquity);
    }
}
