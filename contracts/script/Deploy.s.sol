// SPDX-License-Identifier: MIT
pragma solidity 0.8.28;

import {Script} from "forge-std/Script.sol";
import {console2} from "forge-std/console2.sol";
import {IPyth} from "../src/interfaces/IPyth.sol";
import {LeashAccount} from "../src/LeashAccount.sol";
import {LeashExecutor} from "../src/LeashExecutor.sol";
import {SessionKeyValidator} from "../src/SessionKeyValidator.sol";
import {PriceHistoryLog} from "../src/PriceHistoryLog.sol";
import {RiskLedger} from "../src/RiskLedger.sol";
import {SP1MockVerifier} from "../src/verifiers/SP1MockVerifier.sol";
import {ISP1Verifier} from "../src/interfaces/ISP1Verifier.sol";
import {MockPyth} from "../src/mocks/MockPyth.sol";
import {MockRouter} from "../src/mocks/MockRouter.sol";
import {MockERC20} from "../src/mocks/MockERC20.sol";
import {MockEntryPoint} from "../src/mocks/MockEntryPoint.sol";
import {LeashTypes} from "../src/lib/LeashTypes.sol";

/// @notice Deploys the demo stack.
/// Set PYTH_ADDRESS and SP1_VERIFIER to use real contracts. If they are unset,
/// the script deploys a mock oracle and the mock verifier so a laptop can boot
/// the stack on Anvil. Groth16 proofs still have to come from the Prover Network;
/// the mock verifier is only for wiring the demo before those proofs exist.
contract Deploy is Script {
    function run() external {
        uint256 key = vm.envOr("PRIVATE_KEY", uint256(0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80));
        address owner = vm.addr(key);
        vm.startBroadcast(key);

        address pythAddr = vm.envOr("PYTH_ADDRESS", address(0));
        if (pythAddr == address(0)) pythAddr = address(new MockPyth());
        address verifierAddr = vm.envOr("SP1_VERIFIER", address(0));
        if (verifierAddr == address(0)) verifierAddr = address(new SP1MockVerifier());

        MockEntryPoint entryPoint = new MockEntryPoint();
        PriceHistoryLog priceLog = new PriceHistoryLog(IPyth(pythAddr));
        RiskLedger ledger = new RiskLedger();
        MockERC20 weth = new MockERC20("Wrapped Ether", "WETH", 18);
        MockERC20 usdc = new MockERC20("USD Coin", "USDC", 6);
        MockRouter router = new MockRouter();
        LeashAccount account = new LeashAccount(owner, address(entryPoint));
        LeashExecutor executor = new LeashExecutor(true);
        SessionKeyValidator validator = new SessionKeyValidator();

        executor.initialize(
            address(account),
            ISP1Verifier(verifierAddr),
            vm.envOr("PROGRAM_VKEY", bytes32(uint256(1))),
            IPyth(pythAddr),
            priceLog,
            ledger
        );
        ledger.setExecutor(address(executor));
        account.installModules(address(validator), address(executor));

        bytes32 wethId = vm.envOr("WETH_PRICE_ID", keccak256("WETH/USD"));
        bytes32 usdcId = vm.envOr("USDC_PRICE_ID", keccak256("USDC/USD"));
        executor.setAsset(0, address(weth), wethId, 18, -8);
        executor.setAsset(1, address(usdc), usdcId, 6, -8);
        executor.setRouter(address(router), true);
        executor.setPolicy(
            LeashTypes.Policy({
                maxVolExposure: 40 ether,
                maxConcentrationBps: 8_000,
                maxDrawdownBps: 3_000,
                maxNotional: 30_000 ether,
                maxSlippageBps: 100,
                maxWindowLoss: 5 ether,
                windowSeconds: 1 days,
                maxTradesPerWindow: 20,
                minHistory: 8,
                maxPriceDeviationBps: 50,
                maxPriceAge: 1 hours,
                quoteToken: address(usdc)
            })
        );

        weth.mint(address(account), 10 ether);
        usdc.mint(address(account), 20_000 * 1e6);

        vm.stopBroadcast();
        console2.log("account", address(account));
        console2.log("executor", address(executor));
        console2.log("priceLog", address(priceLog));
        console2.log("pyth", pythAddr);
        console2.log("router", address(router));
        console2.log("weth", address(weth));
        console2.log("usdc", address(usdc));
    }
}
