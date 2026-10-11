// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {IERC7579Module, MODULE_TYPE_EXECUTOR} from "./interfaces/IERC7579.sol";
import {IPyth} from "./interfaces/IPyth.sol";
import {ISP1Verifier} from "./interfaces/ISP1Verifier.sol";
import {ISwapRouter} from "./interfaces/ISwapRouter.sol";
import {Commitments} from "./lib/Commitments.sol";
import {LeashTypes} from "./lib/LeashTypes.sol";
import {RiskMath} from "./lib/RiskMath.sol";
import {PriceHistoryLog} from "./PriceHistoryLog.sol";
import {RiskLedger} from "./RiskLedger.sol";

interface ILeashAccount {
    function executeFromExecutor(address target, uint256 value, bytes calldata data) external returns (bytes memory);
}

interface IERC20Like {
    function balanceOf(address) external view returns (uint256);
    function approve(address, uint256) external returns (bool);
}

/// @notice ERC-7579 executor. The session-key validator may only call
/// `executeGuarded`. Proof and oracle checks live here, in the execution phase,
/// because ERC-7562 forbids `validateUserOp` from reading Pyth or the verifier.
contract LeashExecutor is IERC7579Module {
    uint8 internal constant DECISION_ALLOW = 1;
    uint256 internal constant ONE = 1e18;

    address public owner;
    address public account;
    ISP1Verifier public verifier;
    bytes32 public programVKey;
    IPyth public pyth;
    PriceHistoryLog public priceLog;
    RiskLedger public ledger;
    /// @dev When false, this deployment is the stateless ablation (baseline B4).
    bool public immutable enforceLedger;

    LeashTypes.Policy public policy;
    bytes32 public policyCommitment;
    uint256 public assetCount;
    mapping(uint256 index => LeashTypes.Asset) public assets;
    mapping(address token => uint256 indexPlusOne) public indexOf;
    mapping(address router => bool) public routers;
    mapping(address account => uint256 nonce) public nonces;

    error NotOwner();
    error NotAccount();
    error DecisionDenied();
    error Expired();
    error PolicyMismatch();
    error ActionMismatch();
    error AssetCount();
    error PriceDeviation();
    error ExpoMismatch();
    error HeadMismatch();
    error ShortHistory();
    error BalanceMismatch();
    error VolMismatch();
    error VolLimit();
    error Concentration();
    error NotionalLimit();
    error Drawdown();
    error WindowLoss();
    error TradeRate();
    error LedgerMismatch();
    error RouterNotAllowed();
    error TokenNotAllowed();
    error MinOut();
    error BadSwap();

    event PolicySet(bytes32 commitment);
    event TradeExecuted(address indexed account, bytes32 actionHash, uint256 amountIn, uint256 amountOut, uint256 volExposure);

    constructor(bool enforceLedger_) {
        enforceLedger = enforceLedger_;
        owner = msg.sender;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    function initialize(
        address account_,
        ISP1Verifier verifier_,
        bytes32 programVKey_,
        IPyth pyth_,
        PriceHistoryLog priceLog_,
        RiskLedger ledger_
    ) external onlyOwner {
        account = account_;
        verifier = verifier_;
        programVKey = programVKey_;
        pyth = pyth_;
        priceLog = priceLog_;
        ledger = ledger_;
    }

    function setPolicy(LeashTypes.Policy calldata next) external onlyOwner {
        policy = next;
        policyCommitment = Commitments.policyCommitment(next);
        emit PolicySet(policyCommitment);
    }

    function setAsset(uint8 index, address token, bytes32 priceId, uint8 decimals, int32 expo) external onlyOwner {
        require(index < 8, "index");
        assets[index] = LeashTypes.Asset({token: token, priceId: priceId, decimals: decimals, expo: expo, allowed: true});
        indexOf[token] = uint256(index) + 1;
        if (uint256(index) + 1 > assetCount) assetCount = uint256(index) + 1;
    }

    function setRouter(address router, bool allowed) external onlyOwner {
        routers[router] = allowed;
    }

    function transferOwnership(address next) external onlyOwner {
        owner = next;
    }

    function onInstall(bytes calldata) external {}

    function onUninstall(bytes calldata) external {}

    function isModuleType(uint256 moduleTypeId) external pure returns (bool) {
        return moduleTypeId == MODULE_TYPE_EXECUTOR;
    }

    function executeGuarded(
        LeashTypes.SwapAction calldata action,
        bytes calldata publicValues,
        bytes calldata proof,
        bytes[] calldata pythUpdates
    ) external payable returns (uint256 amountOut) {
        if (msg.sender != account) revert NotAccount();
        uint256 fee = pyth.getUpdateFee(pythUpdates);
        if (pythUpdates.length != 0) pyth.updatePriceFeeds{value: fee}(pythUpdates);

        verifier.verifyProof(programVKey, publicValues, proof);
        LeashTypes.PublicValues memory pv = abi.decode(publicValues, (LeashTypes.PublicValues));
        if (pv.decision != DECISION_ALLOW) revert DecisionDenied();
        if (pv.expiry < block.timestamp || action.deadline < block.timestamp) revert Expired();
        if (pv.policyCommitment != policyCommitment) revert PolicyMismatch();
        if (pv.assetCount != assetCount) revert AssetCount();
        if (!routers[action.router]) revert RouterNotAllowed();

        uint256 nonce = nonces[account];
        bytes32 expected = Commitments.actionHash(
            block.chainid, account, action.router, action.tokenIn, action.tokenOut, action.fee, action.amountIn, action.deadline, nonce
        );
        if (pv.actionHash != expected) revert ActionMismatch();
        nonces[account] = nonce + 1;

        uint256 inIndex = _index(action.tokenIn);
        uint256 outIndex = _index(action.tokenOut);
        if (inIndex == outIndex) revert BadSwap();

        uint256 fair = _checkAssetsAndRisk(action, pv, inIndex, outIndex);
        uint256 minAmount = RiskMath.minOut(fair, policy.maxSlippageBps);
        uint256 equityBefore = _equity(pv);

        amountOut = _swap(action, minAmount);
        if (amountOut < minAmount) revert MinOut();

        if (enforceLedger) {
            uint256 equityAfter = _equityAfterSwap(pv, inIndex, outIndex, action.amountIn, amountOut);
            uint256 loss = equityBefore > equityAfter ? equityBefore - equityAfter : 0;
            int256 pnl = int256(equityAfter) - int256(equityBefore);
            ledger.applyTrade(
                account,
                pnl,
                equityAfter,
                loss,
                uint64(block.timestamp),
                policy.windowSeconds,
                policy.maxWindowLoss,
                policy.maxTradesPerWindow
            );
        }
        emit TradeExecuted(account, pv.actionHash, action.amountIn, amountOut, pv.volExposure);
    }

    function _index(address token) internal view returns (uint256) {
        uint256 plus = indexOf[token];
        if (plus == 0) revert TokenNotAllowed();
        return plus - 1;
    }

    function _checkAssetsAndRisk(LeashTypes.SwapAction calldata action, LeashTypes.PublicValues memory pv, uint256 inIndex, uint256 outIndex)
        internal
        view
        returns (uint256 fair)
    {
        uint256 vol;
        uint256 preVol;
        uint256 totalPost;
        uint256 maxNonQuote;
        for (uint256 i = 0; i < assetCount; ++i) {
            LeashTypes.Asset memory asset = assets[i];
            IPyth.Price memory px = pyth.getPriceNoOlderThan(asset.priceId, policy.maxPriceAge);
            if (px.expo != asset.expo) revert ExpoMismatch();
            if (!_close(px.price, pv.provenPrices[i], policy.maxPriceDeviationBps)) revert PriceDeviation();

            uint256 len = priceLog.lengthOf(asset.priceId);
            if (len < policy.minHistory) revert ShortHistory();
            if (priceLog.heads(asset.priceId, 0) != pv.headStart[i]) revert HeadMismatch();
            if (priceLog.heads(asset.priceId, len - 1) != pv.headEnd[i]) revert HeadMismatch();

            uint256 pre = IERC20Like(asset.token).balanceOf(account);
            uint256 post = pre;
            if (i == inIndex) {
                if (pre < action.amountIn) revert BalanceMismatch();
                post = pre - action.amountIn;
            }
            uint256 px1 = RiskMath.price1e18(pv.provenPrices[i], asset.expo);
            if (i == outIndex) {
                LeashTypes.Asset memory tin = assets[inIndex];
                fair = RiskMath.fairOut(
                    action.amountIn,
                    tin.decimals,
                    RiskMath.price1e18(pv.provenPrices[inIndex], tin.expo),
                    asset.decimals,
                    px1
                );
                post = pre + fair;
            }
            if (post != pv.balances[i]) revert BalanceMismatch();

            uint256 expPost = RiskMath.exposure(post, px1, asset.decimals);
            uint256 expPre = RiskMath.exposure(pre, px1, asset.decimals);
            vol += expPost * pv.sigmas[i] / ONE;
            preVol += expPre * pv.sigmas[i] / ONE;
            totalPost += expPost;
            if (asset.token != policy.quoteToken && expPost > maxNonQuote) maxNonQuote = expPost;
        }
        if (vol != pv.volExposure) revert VolMismatch();
        // Selling into the quote asset without raising V passes the risk-budget limits.
        bool reducesRisk = action.tokenOut == policy.quoteToken && vol <= preVol;
        if (vol > policy.maxVolExposure && !reducesRisk) revert VolLimit();

        uint256 notion = RiskMath.exposure(
            action.amountIn,
            RiskMath.price1e18(pv.provenPrices[inIndex], assets[inIndex].expo),
            assets[inIndex].decimals
        );
        if (notion > policy.maxNotional) revert NotionalLimit();
        if (!reducesRisk && totalPost != 0 && maxNonQuote * 10_000 / totalPost > policy.maxConcentrationBps) {
            revert Concentration();
        }

        if (enforceLedger) {
            RiskLedger.State memory s = ledger.stateOf(account);
            if (pv.cumulativePnl != s.cumulativePnl || pv.peakEquity != s.peakEquity || pv.windowLoss != s.windowLoss)
                revert LedgerMismatch();
            if (pv.windowStart != s.windowStart || pv.tradesInWindow != s.tradesInWindow) revert LedgerMismatch();
            if (s.windowLoss >= policy.maxWindowLoss) revert WindowLoss();
            if (s.tradesInWindow >= policy.maxTradesPerWindow) revert TradeRate();

            uint256 equity = _equityFromPre(pv, inIndex, outIndex, action.amountIn, fair);
            uint256 peak = s.peakEquity == 0 ? equity : s.peakEquity;
            uint256 dd = peak > equity ? (peak - equity) * 10_000 / peak : 0;
            if (dd > policy.maxDrawdownBps && !reducesRisk) revert Drawdown();
        }
    }

    function _equity(LeashTypes.PublicValues memory pv) internal view returns (uint256 equity) {
        for (uint256 i = 0; i < assetCount; ++i) {
            uint256 pre = IERC20Like(assets[i].token).balanceOf(account);
            equity += RiskMath.exposure(pre, RiskMath.price1e18(pv.provenPrices[i], assets[i].expo), assets[i].decimals);
        }
    }

    function _equityFromPre(LeashTypes.PublicValues memory pv, uint256, uint256, uint256, uint256) internal view returns (uint256) {
        return _equity(pv);
    }

    function _equityAfterSwap(LeashTypes.PublicValues memory pv, uint256, uint256, uint256, uint256)
        internal
        view
        returns (uint256 equity)
    {
        for (uint256 i = 0; i < assetCount; ++i) {
            uint256 bal = IERC20Like(assets[i].token).balanceOf(account);
            equity += RiskMath.exposure(bal, RiskMath.price1e18(pv.provenPrices[i], assets[i].expo), assets[i].decimals);
        }
    }

    function _swap(LeashTypes.SwapAction calldata action, uint256 minAmount) internal returns (uint256 amountOut) {
        uint256 beforeOut = IERC20Like(action.tokenOut).balanceOf(account);
        ILeashAccount(account).executeFromExecutor(
            action.tokenIn, 0, abi.encodeWithSelector(IERC20Like.approve.selector, action.router, action.amountIn)
        );
        ISwapRouter.ExactInputSingleParams memory params = ISwapRouter.ExactInputSingleParams({
            tokenIn: action.tokenIn,
            tokenOut: action.tokenOut,
            fee: action.fee,
            recipient: account,
            amountIn: action.amountIn,
            amountOutMinimum: minAmount,
            sqrtPriceLimitX96: 0
        });
        ILeashAccount(account).executeFromExecutor(
            action.router, 0, abi.encodeWithSelector(ISwapRouter.exactInputSingle.selector, params)
        );
        amountOut = IERC20Like(action.tokenOut).balanceOf(account) - beforeOut;
    }

    function _close(int64 live, int64 proven, uint256 bps) internal pure returns (bool) {
        if (live <= 0 || proven <= 0) return false;
        uint256 a = uint256(uint64(live));
        uint256 b = uint256(uint64(proven));
        uint256 diff = a > b ? a - b : b - a;
        return diff * 10_000 <= a * bps;
    }
}

