// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Test} from "forge-std/Test.sol";
import {LeashAccount} from "../src/LeashAccount.sol";
import {LeashExecutor} from "../src/LeashExecutor.sol";
import {SessionKeyValidator} from "../src/SessionKeyValidator.sol";
import {PriceHistoryLog} from "../src/PriceHistoryLog.sol";
import {RiskLedger} from "../src/RiskLedger.sol";
import {SP1HonestVerifier} from "../src/verifiers/SP1HonestVerifier.sol";
import {SP1MockVerifier} from "../src/verifiers/SP1MockVerifier.sol";
import {MockERC20} from "../src/mocks/MockERC20.sol";
import {MockPyth} from "../src/mocks/MockPyth.sol";
import {MockRouter} from "../src/mocks/MockRouter.sol";
import {MockEntryPoint} from "../src/mocks/MockEntryPoint.sol";
import {LeashTypes} from "../src/lib/LeashTypes.sol";
import {RiskMath} from "../src/lib/RiskMath.sol";
import {OnChainEwma} from "../src/baselines/OnChainEwma.sol";
import {SignedAttestationGuard} from "../src/baselines/SignedAttestationGuard.sol";
import {StaticSessionGuard} from "../src/baselines/StaticSessionGuard.sol";
import {PackedUserOperation} from "../src/interfaces/IERC7579.sol";

contract LeashTest is Test {
    uint256 internal constant NOW = 1_700_000_000;
    bytes32 internal constant VKEY = bytes32(uint256(0x1234));
    bytes32 internal constant WETH_ID = keccak256("WETH/USD");
    bytes32 internal constant USDC_ID = keccak256("USDC/USD");

    LeashAccount account;
    LeashExecutor executor;
    LeashExecutor stateless;
    SessionKeyValidator validator;
    PriceHistoryLog priceLog;
    RiskLedger ledger;
    SP1HonestVerifier verifier;
    MockPyth pyth;
    MockRouter router;
    MockEntryPoint entryPoint;
    MockERC20 weth;
    MockERC20 usdc;
    address session;
    uint256 sessionPk;

    function setUp() public {
        vm.warp(NOW);
        sessionPk = 0xA11CE;
        session = vm.addr(sessionPk);
        pyth = new MockPyth();
        priceLog = new PriceHistoryLog(pyth);
        ledger = new RiskLedger();
        verifier = new SP1HonestVerifier();
        weth = new MockERC20("Wrapped Ether", "WETH", 18);
        usdc = new MockERC20("USD Coin", "USDC", 6);
        router = new MockRouter();
        entryPoint = new MockEntryPoint();
        account = new LeashAccount(address(this), address(entryPoint));
        executor = new LeashExecutor(true);
        stateless = new LeashExecutor(false);
        validator = new SessionKeyValidator();

        executor.initialize(address(account), verifier, VKEY, pyth, priceLog, ledger);
        stateless.initialize(address(account), verifier, VKEY, pyth, priceLog, ledger);
        ledger.setExecutor(address(executor));
        account.installModules(address(validator), address(executor));
        account.setSessionKey(session);

        executor.setAsset(0, address(weth), WETH_ID, 18, -8);
        executor.setAsset(1, address(usdc), USDC_ID, 6, -8);
        executor.setRouter(address(router), true);
        stateless.setAsset(0, address(weth), WETH_ID, 18, -8);
        stateless.setAsset(1, address(usdc), USDC_ID, 6, -8);
        stateless.setRouter(address(router), true);
    }

    function test_ewma_matches_guest_fixture() public pure {
        int64[] memory prices = new int64[](3);
        prices[0] = 1000;
        prices[1] = 1100;
        prices[2] = 1210;
        assertEq(RiskMath.ewmaSigma(prices), 34_117_444_218_463_961);
    }

    function test_calm_swap_is_allowed() public {
        string memory json = _scenario("calm", 0, 0, 0, 0, 0, 0, 0);
        _applyPolicy(executor, json);
        _recordHistory(json);
        _mintFromScenario(json);
        uint256 fair = _fairOut(json, true);
        router.setPayout(fair);

        uint256 usdcBefore = usdc.balanceOf(address(account));
        _execute(executor, json);
        assertEq(usdc.balanceOf(address(account)), usdcBefore + fair);
        assertEq(executor.nonces(address(account)), 1);
        assertEq(ledger.stateOf(address(account)).tradesInWindow, 1);
    }

    function test_volatile_buy_is_blocked() public {
        string memory json = _scenario("volatile_buy", 0, 0, 0, 0, 0, 0, 0);
        _applyPolicy(executor, json);
        _recordHistory(json);
        _mintFromScenario(json);
        bytes memory pv = vm.parseJsonBytes(json, ".public_values");
        bytes memory proof = verifier.prove(VKEY, pv);
        vm.prank(address(account));
        vm.expectRevert(LeashExecutor.DecisionDenied.selector);
        executor.executeGuarded(_action(json), pv, proof, new bytes[](0));
    }

    function test_lying_guest_is_caught_by_vol_limit() public {
        string memory json = _scenario("vol_spike_buy", 0, 0, 0, 0, 0, 0, 0);
        assertFalse(vm.parseJsonBool(json, ".allowed"));
        _applyPolicy(executor, json);
        _recordHistory(json);
        _mintFromScenario(json);
        bytes memory pv = vm.parseJsonBytes(json, ".public_values");
        // A buggy guest that sets the allow bit on a trade over the volatility budget.
        pv[4 * 32 + 31] = 0x01;
        bytes memory proof = verifier.prove(VKEY, pv);
        vm.prank(address(account));
        vm.expectRevert(LeashExecutor.VolLimit.selector);
        executor.executeGuarded(_action(json), pv, proof, new bytes[](0));
    }

    function test_derisk_over_vol_budget_is_allowed() public {
        string memory json = _scenario("volatile_sell", 0, 0, 0, 0, 0, 0, 0);
        assertTrue(vm.parseJsonBool(json, ".allowed"));
        assertGt(_dec(vm.parseJsonString(json, ".vol_exposure")), _dec(vm.parseJsonString(json, ".policy.max_vol_exposure")));
        _applyPolicy(executor, json);
        _recordHistory(json);
        _mintFromScenario(json);
        router.setPayout(_fairOut(json, true));
        _execute(executor, json);
        assertEq(executor.nonces(address(account)), 1);
    }

    function test_forged_price_history_is_rejected() public {
        string memory json = _scenario("calm", 0, 0, 0, 0, 0, 0, 0);
        _applyPolicy(executor, json);
        _recordHistory(json);
        // Append one extra point the proof does not cover.
        pyth.setPrice(WETH_ID, 123, 1, -8, NOW + 1);
        priceLog.record(new bytes[](0), WETH_ID);
        // Restore the live price to the proven one so the deviation check is not the reason.
        uint256[] memory prices = vm.parseJsonUintArray(json, ".weth_price");
        uint256[] memory times = vm.parseJsonUintArray(json, ".weth_time");
        pyth.setPrice(WETH_ID, int64(uint64(prices[prices.length - 1])), 50_000, -8, times[times.length - 1]);
        _mintFromScenario(json);
        router.setPayout(_fairOut(json, true));
        bytes memory pv = vm.parseJsonBytes(json, ".public_values");
        bytes memory proof = verifier.prove(VKEY, pv);
        vm.prank(address(account));
        vm.expectRevert(LeashExecutor.HeadMismatch.selector);
        executor.executeGuarded(_action(json), pv, proof, new bytes[](0));
    }

    function test_price_log_refuses_a_repeated_publish_time() public {
        pyth.setPrice(WETH_ID, 200_000_000_000, 50_000, -8, NOW);
        priceLog.record(new bytes[](0), WETH_ID);
        // Re-recording the same Pyth price would add a zero return and pull sigma down.
        vm.expectRevert(PriceHistoryLog.StalePrice.selector);
        priceLog.record(new bytes[](0), WETH_ID);
        pyth.setPrice(WETH_ID, 200_000_000_000, 50_000, -8, NOW - 60);
        vm.expectRevert(PriceHistoryLog.StalePrice.selector);
        priceLog.record(new bytes[](0), WETH_ID);
        pyth.setPrice(WETH_ID, 200_100_000_000, 50_000, -8, NOW + 60);
        priceLog.record(new bytes[](0), WETH_ID);
        assertEq(priceLog.lengthOf(WETH_ID), 2);
    }

    function test_tampered_public_values_fail_the_honest_verifier() public {
        string memory json = _scenario("calm", 0, 0, 0, 0, 0, 0, 0);
        _applyPolicy(executor, json);
        _recordHistory(json);
        _mintFromScenario(json);
        router.setPayout(_fairOut(json, true));
        bytes memory pv = vm.parseJsonBytes(json, ".public_values");
        bytes memory proof = verifier.prove(VKEY, pv);
        pv[pv.length - 1] ^= 0x01;
        LeashTypes.SwapAction memory action = _action(json);
        vm.prank(address(account));
        vm.expectRevert(SP1HonestVerifier.BadProof.selector);
        executor.executeGuarded(action, pv, proof, new bytes[](0));
    }

    function test_mock_verifier_accepts_any_proof_bytes() public {
        SP1MockVerifier mock = new SP1MockVerifier();
        mock.verifyProof(VKEY, hex"1234", "");
    }

    function test_replay_is_rejected() public {
        string memory json = _scenario("calm", 0, 0, 0, 0, 0, 0, 0);
        _applyPolicy(executor, json);
        _recordHistory(json);
        _mintFromScenario(json);
        router.setPayout(_fairOut(json, true));
        bytes memory pv = vm.parseJsonBytes(json, ".public_values");
        bytes memory proof = verifier.prove(VKEY, pv);
        LeashTypes.SwapAction memory action = _action(json);
        vm.prank(address(account));
        executor.executeGuarded(action, pv, proof, new bytes[](0));
        vm.expectRevert(LeashExecutor.ActionMismatch.selector);
        vm.prank(address(account));
        executor.executeGuarded(action, pv, proof, new bytes[](0));
    }

    function test_unknown_router_is_rejected() public {
        string memory json = _scenario("calm", 0, 0, 0, 0, 0, 0, 0);
        _applyPolicy(executor, json);
        _recordHistory(json);
        _mintFromScenario(json);
        LeashTypes.SwapAction memory action = _action(json);
        action.router = address(0xBEEF);
        bytes memory pv = vm.parseJsonBytes(json, ".public_values");
        bytes memory proof = verifier.prove(VKEY, pv);
        vm.prank(address(account));
        vm.expectRevert(LeashExecutor.RouterNotAllowed.selector);
        executor.executeGuarded(action, pv, proof, new bytes[](0));
    }

    function test_session_key_can_submit_and_cannot_change_modules() public {
        string memory json = _scenario("calm", 0, 0, 0, 0, 0, 0, 0);
        _applyPolicy(executor, json);
        _recordHistory(json);
        _mintFromScenario(json);
        router.setPayout(_fairOut(json, true));

        bytes memory inner = _guardedCalldata(json);
        bytes memory callData = abi.encodeWithSelector(LeashAccount.execute.selector, address(executor), uint256(0), inner);
        PackedUserOperation memory op = _op(callData);
        bytes32 hash = entryPoint.hashOp(op);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(sessionPk, hash);
        op.signature = abi.encodePacked(r, s, v);
        entryPoint.handleOp(op);
        assertEq(executor.nonces(address(account)), 1);

        vm.prank(session);
        vm.expectRevert(LeashAccount.NotOwner.selector);
        account.setSessionKey(address(0x1234));
    }

    function test_session_key_cannot_call_a_raw_transfer() public {
        bytes memory inner = abi.encodeWithSelector(MockERC20.transfer.selector, address(0xBEEF), uint256(1));
        bytes memory callData = abi.encodeWithSelector(LeashAccount.execute.selector, address(weth), uint256(0), inner);
        PackedUserOperation memory op = _op(callData);
        bytes32 hash = entryPoint.hashOp(op);
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(sessionPk, hash);
        op.signature = abi.encodePacked(r, s, v);
        vm.expectRevert(bytes("validation"));
        entryPoint.handleOp(op);
    }

    function test_salami_drain_stops_at_the_loss_cap() public {
        string memory first = _scenario("calm", 0, 0, 0, 0, 0, 0, 0);
        _applyPolicy(executor, first);
        _recordHistory(first);
        _mintFromScenario(first);

        uint256 fair = _fairOut(first, true);
        uint256 minAmount = RiskMath.minOut(fair, _dec(vm.parseJsonString(first, ".policy.max_slippage_bps")));
        // Pay the minimum, so each trade realizes about `slippage` of loss.
        router.setPayout(minAmount);
        _execute(executor, first);

        // Keep trading until the ledger refuses. Bound the loop so a bug cannot hang the test.
        uint256 wethBal = weth.balanceOf(address(account));
        uint256 usdcBal = usdc.balanceOf(address(account));
        bool stopped;
        for (uint256 nonce = 1; nonce < 12; ++nonce) {
            RiskLedger.State memory s = ledger.stateOf(address(account));
            string memory next = _scenario(
                "calm",
                nonce,
                wethBal,
                usdcBal,
                s.windowLoss,
                s.peakEquity,
                s.tradesInWindow,
                s.cumulativePnl
            );
            if (!vm.parseJsonBool(next, ".allowed")) {
                stopped = true;
                break;
            }
            try this.exec(next) {
                wethBal = weth.balanceOf(address(account));
                usdcBal = usdc.balanceOf(address(account));
            } catch {
                stopped = true;
                break;
            }
        }
        assertTrue(stopped, "loss cap never engaged");
        assertLe(ledger.stateOf(address(account)).windowLoss, _dec(vm.parseJsonString(first, ".policy.max_window_loss")));
    }

    function exec(string memory json) external {
        _execute(executor, json);
    }

    function test_stateless_ablation_does_not_track_loss() public {
        string memory json = _scenario("calm", 0, 0, 0, 0, 0, 0, 0);
        _applyPolicy(stateless, json);
        _recordHistory(json);
        _mintFromScenario(json);
        // Point the account at the stateless executor for the callback.
        account.installModules(address(validator), address(stateless));
        router.setPayout(RiskMath.minOut(_fairOut(json, true), 100));
        _execute(stateless, json);
        assertEq(ledger.stateOf(address(account)).tradesInWindow, 0);
    }

    function test_stolen_verifier_key_drains_the_signed_baseline() public {
        uint256 pk = 0xBEEF;
        SignedAttestationGuard guard = new SignedAttestationGuard(vm.addr(pk));
        weth.mint(address(guard), 1 ether);
        bytes memory data = abi.encodeWithSelector(MockERC20.transfer.selector, address(0xBAD), uint256(1 ether));
        bytes32 digest = keccak256(abi.encode(block.chainid, address(this), address(weth), uint256(0), keccak256(data), uint256(0)));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(pk, digest);
        guard.execute(address(weth), 0, data, 0, abi.encodePacked(r, s, v));
        assertEq(weth.balanceOf(address(0xBAD)), 1 ether);
    }

    function test_static_guard_blocks_unknown_target() public {
        StaticSessionGuard guard = new StaticSessionGuard(address(this), 1 ether);
        vm.expectRevert(StaticSessionGuard.NotAllowed.selector);
        guard.execute(address(weth), 0, "", 1);
    }

    function testFuzz_minOut_never_exceeds_fair(uint128 fair, uint16 bps) public pure {
        bps = bps % 10_000;
        if (bps == 10_000) return;
        assertLe(RiskMath.minOut(fair, bps), fair);
    }

    function test_gas_crossover_samples() public {
        OnChainEwma ewma = new OnChainEwma();
        uint256[4] memory widths = [uint256(8), 32, 64, 128];
        for (uint256 w = 0; w < widths.length; ++w) {
            int64[] memory prices = new int64[](widths[w]);
            for (uint256 i = 0; i < widths[w]; ++i) {
                prices[i] = int64(int256(1_000_000 + i));
            }
            vm.cool(address(ewma));
            uint256 gasBefore = gasleft();
            ewma.sigma(prices);
            uint256 used = gasBefore - gasleft();
            emit log_named_uint(string.concat("ewma_gas_", vm.toString(widths[w])), used);

            ewma.load(prices);
            vm.cool(address(ewma));
            gasBefore = gasleft();
            uint256 fromStorage = ewma.sigmaFromStorage();
            used = gasBefore - gasleft();
            assertEq(fromStorage, ewma.sigma(prices));
            emit log_named_uint(string.concat("ewma_storage_gas_", vm.toString(widths[w])), used);
        }
    }

    function test_gas_trade_path_samples() public {
        string memory json = _scenario("calm", 0, 0, 0, 0, 0, 0, 0);
        _applyPolicy(executor, json);
        _recordHistory(json);
        _mintFromScenario(json);
        router.setPayout(_fairOut(json, true));
        bytes memory pv = vm.parseJsonBytes(json, ".public_values");
        bytes memory proof = verifier.prove(VKEY, pv);
        LeashTypes.SwapAction memory action = _action(json);

        _coolAll();
        uint256 gasBefore = gasleft();
        verifier.verifyProof(VKEY, pv, proof);
        emit log_named_uint("stand_in_verifier_gas", gasBefore - gasleft());

        _coolAll();
        vm.prank(address(account));
        gasBefore = gasleft();
        executor.executeGuarded(action, pv, proof, new bytes[](0));
        emit log_named_uint("execute_guarded_first_trade_gas", gasBefore - gasleft());

        // A second trade writes ledger slots that already exist.
        RiskLedger.State memory s = ledger.stateOf(address(account));
        string memory next = _scenario(
            "calm",
            1,
            weth.balanceOf(address(account)),
            usdc.balanceOf(address(account)),
            s.windowLoss,
            s.peakEquity,
            s.tradesInWindow,
            s.cumulativePnl
        );
        router.setPayout(_fairOut(next, true));
        bytes memory pv2 = vm.parseJsonBytes(next, ".public_values");
        bytes memory proof2 = verifier.prove(VKEY, pv2);
        LeashTypes.SwapAction memory action2 = _action(next);
        _coolAll();
        vm.prank(address(account));
        gasBefore = gasleft();
        executor.executeGuarded(action2, pv2, proof2, new bytes[](0));
        emit log_named_uint("execute_guarded_next_trade_gas", gasBefore - gasleft());

        uint256[] memory times = vm.parseJsonUintArray(json, ".weth_time");
        pyth.setPrice(WETH_ID, 200_500_000_000, 50_000, -8, times[times.length - 1] + 60);
        _coolAll();
        gasBefore = gasleft();
        priceLog.record(new bytes[](0), WETH_ID);
        emit log_named_uint("price_log_record_gas", gasBefore - gasleft());
    }

    function _coolAll() internal {
        vm.cool(address(executor));
        vm.cool(address(ledger));
        vm.cool(address(priceLog));
        vm.cool(address(pyth));
        vm.cool(address(verifier));
        vm.cool(address(router));
        vm.cool(address(account));
        vm.cool(address(weth));
        vm.cool(address(usdc));
    }

    function _scenario(
        string memory name,
        uint256 nonce,
        uint256 wethBal,
        uint256 usdcBal,
        uint256 windowLoss,
        uint256 peak,
        uint256 trades,
        int256 pnl
    ) internal returns (string memory) {
        string memory bin = string.concat(vm.projectRoot(), "/../prover/target/debug/leash-risk");
        if (wethBal == 0) {
            string[] memory cmd = new string[](19);
            cmd[0] = bin;
            cmd[1] = "scenario";
            cmd[2] = name;
            cmd[3] = "--account";
            cmd[4] = vm.toString(address(account));
            cmd[5] = "--router";
            cmd[6] = vm.toString(address(router));
            cmd[7] = "--weth";
            cmd[8] = vm.toString(address(weth));
            cmd[9] = "--usdc";
            cmd[10] = vm.toString(address(usdc));
            cmd[11] = "--now";
            cmd[12] = vm.toString(NOW);
            cmd[13] = "--nonce";
            cmd[14] = vm.toString(nonce);
            cmd[15] = "--chain-id";
            cmd[16] = vm.toString(block.chainid);
            cmd[17] = "--amount";
            cmd[18] = "100000000000000000";
            return string(vm.ffi(cmd));
        }
        string[] memory full = new string[](33);
        full[0] = bin;
        full[1] = "scenario";
        full[2] = name;
        full[3] = "--account";
        full[4] = vm.toString(address(account));
        full[5] = "--router";
        full[6] = vm.toString(address(router));
        full[7] = "--weth";
        full[8] = vm.toString(address(weth));
        full[9] = "--usdc";
        full[10] = vm.toString(address(usdc));
        full[11] = "--now";
        full[12] = vm.toString(NOW);
        full[13] = "--nonce";
        full[14] = vm.toString(nonce);
        full[15] = "--chain-id";
        full[16] = vm.toString(block.chainid);
        full[17] = "--amount";
        full[18] = "100000000000000000";
        full[19] = "--weth-balance";
        full[20] = vm.toString(wethBal);
        full[21] = "--usdc-balance";
        full[22] = vm.toString(usdcBal);
        full[23] = "--window-loss";
        full[24] = vm.toString(windowLoss);
        full[25] = "--peak-equity";
        full[26] = vm.toString(peak);
        full[27] = "--trades";
        full[28] = vm.toString(trades);
        full[29] = "--cumulative-pnl";
        full[30] = vm.toString(pnl);
        full[31] = "--window-start";
        full[32] = vm.toString(NOW);
        return string(vm.ffi(full));
    }

    function _applyPolicy(LeashExecutor target, string memory json) internal {
        LeashTypes.Policy memory p;
        p.maxVolExposure = _dec(vm.parseJsonString(json, ".policy.max_vol_exposure"));
        p.maxConcentrationBps = vm.parseJsonUint(json, ".policy.max_concentration_bps");
        p.maxDrawdownBps = vm.parseJsonUint(json, ".policy.max_drawdown_bps");
        p.maxNotional = _dec(vm.parseJsonString(json, ".policy.max_notional"));
        p.maxSlippageBps = vm.parseJsonUint(json, ".policy.max_slippage_bps");
        p.maxWindowLoss = _dec(vm.parseJsonString(json, ".policy.max_window_loss"));
        p.windowSeconds = uint64(vm.parseJsonUint(json, ".policy.window_seconds"));
        p.maxTradesPerWindow = uint32(vm.parseJsonUint(json, ".policy.max_trades_per_window"));
        p.minHistory = uint32(vm.parseJsonUint(json, ".policy.min_history"));
        p.maxPriceDeviationBps = uint32(vm.parseJsonUint(json, ".policy.max_price_deviation_bps"));
        p.maxPriceAge = uint64(vm.parseJsonUint(json, ".policy.max_price_age"));
        p.quoteToken = address(usdc);
        target.setPolicy(p);
        if (target == executor) {
            // The salami loop tightens the cap via the guest flag only when balances are passed.
            // The on-chain policy is whatever we just set, which for the first call is the default.
        }
    }

    function _recordHistory(string memory json) internal {
        _record(json, ".weth", WETH_ID);
        _record(json, ".usdc", USDC_ID);
    }

    function _record(string memory json, string memory prefix, bytes32 id) internal {
        uint256[] memory prices = vm.parseJsonUintArray(json, string.concat(prefix, "_price"));
        uint256[] memory confs = vm.parseJsonUintArray(json, string.concat(prefix, "_conf"));
        uint256[] memory times = vm.parseJsonUintArray(json, string.concat(prefix, "_time"));
        for (uint256 i = 0; i < prices.length; ++i) {
            pyth.setPrice(id, int64(uint64(prices[i])), uint64(confs[i]), -8, times[i]);
            priceLog.record(new bytes[](0), id);
        }
    }

    function _mintFromScenario(string memory json) internal {
        weth.mint(address(account), _dec(vm.parseJsonString(json, ".weth_balance")));
        usdc.mint(address(account), _dec(vm.parseJsonString(json, ".usdc_balance")));
    }

    function _execute(LeashExecutor target, string memory json) internal {
        bytes memory pv = vm.parseJsonBytes(json, ".public_values");
        bytes memory proof = verifier.prove(VKEY, pv);
        vm.prank(address(account));
        target.executeGuarded(_action(json), pv, proof, new bytes[](0));
    }

    function _action(string memory json) internal view returns (LeashTypes.SwapAction memory action) {
        uint256 inIndex = vm.parseJsonUint(json, ".token_in_index");
        action = LeashTypes.SwapAction({
            router: address(router),
            tokenIn: inIndex == 0 ? address(weth) : address(usdc),
            tokenOut: inIndex == 0 ? address(usdc) : address(weth),
            fee: uint24(vm.parseJsonUint(json, ".fee")),
            amountIn: _dec(vm.parseJsonString(json, ".amount_in")),
            deadline: uint64(vm.parseJsonUint(json, ".deadline"))
        });
    }

    function _fairOut(string memory json, bool wethIn) internal pure returns (uint256) {
        uint256[] memory wethPx = vm.parseJsonUintArray(json, ".weth_price");
        uint256[] memory usdcPx = vm.parseJsonUintArray(json, ".usdc_price");
        uint256 amount = _dec(vm.parseJsonString(json, ".amount_in"));
        uint256 pxW = RiskMath.price1e18(int64(uint64(wethPx[wethPx.length - 1])), -8);
        uint256 pxU = RiskMath.price1e18(int64(uint64(usdcPx[usdcPx.length - 1])), -8);
        if (wethIn) return RiskMath.fairOut(amount, 18, pxW, 6, pxU);
        return RiskMath.fairOut(amount, 6, pxU, 18, pxW);
    }

    function _guardedCalldata(string memory json) internal view returns (bytes memory) {
        bytes memory pv = vm.parseJsonBytes(json, ".public_values");
        bytes memory proof = verifier.prove(VKEY, pv);
        return abi.encodeWithSelector(LeashExecutor.executeGuarded.selector, _action(json), pv, proof, new bytes[](0));
    }

    function _op(bytes memory callData) internal view returns (PackedUserOperation memory op) {
        op.sender = address(account);
        op.nonce = account.nonce();
        op.callData = callData;
    }

    function _dec(string memory s) internal pure returns (uint256 r) {
        bytes memory b = bytes(s);
        for (uint256 i = 0; i < b.length; ++i) {
            require(b[i] >= "0" && b[i] <= "9", "dec");
            r = r * 10 + uint8(b[i]) - 48;
        }
    }
}
