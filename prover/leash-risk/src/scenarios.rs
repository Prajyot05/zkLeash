//! Built-in inputs shared by the CLI, the Foundry tests (via `leash-risk scenario`),
//! and the benchmark harness. Keeping one generator avoids a second copy of the
//! price series drifting away from the guest.

use alloc::vec::Vec;

use crate::evaluate;
use crate::types::*;

#[derive(Clone, Debug)]
pub struct ScenarioAddrs {
    pub account: [u8; 20],
    pub router: [u8; 20],
    pub weth: [u8; 20],
    pub usdc: [u8; 20],
}

#[derive(Clone, Debug)]
pub struct Scenario {
    pub name: &'static str,
    pub input: GuestInput,
    pub evaluation: Evaluation,
}

pub fn calm(addrs: ScenarioAddrs, amount_in: u128, now: u64) -> Scenario {
    build("calm", addrs, amount_in, now, false, policy_defaults)
}

pub fn volatile_buy(addrs: ScenarioAddrs, now: u64) -> Scenario {
    let mut s = build(
        "volatile_buy",
        addrs,
        20_000 * 10u128.pow(6),
        now,
        true,
        policy_defaults,
    );
    // Spend USDC to buy WETH.
    s.input.action.token_in_index = 1;
    s.input.action.token_out_index = 0;
    s.input.action.amount_in = 20_000 * 10u128.pow(6);
    s.evaluation = evaluate(&s.input);
    s
}

fn policy_defaults(quote: [u8; 20]) -> Policy {
    Policy {
        max_vol_exposure: 50_000 * ONE,
        max_concentration_bps: 8_000,
        max_drawdown_bps: 3_000,
        max_notional: 30_000 * ONE,
        max_slippage_bps: 100,
        // Five dollars. One fair trade fits; a few 1% slipped trades do not.
        max_window_loss: 5 * ONE,
        window_seconds: 86_400,
        max_trades_per_window: 20,
        min_history: 8,
        max_price_deviation_bps: 50,
        max_price_age: 3_600,
        quote_token: quote,
        quote_index: 1,
    }
}

fn build(
    name: &'static str,
    addrs: ScenarioAddrs,
    amount_in: u128,
    now: u64,
    jumpy: bool,
    policy_fn: fn([u8; 20]) -> Policy,
) -> Scenario {
    let weth_prices = if jumpy {
        jumpy_prices(now)
    } else {
        calm_prices(200_000_000_000, now)
    };
    let usdc_prices = calm_prices(100_000_000, now);
    let input = GuestInput {
        policy: policy_fn(addrs.usdc),
        ledger: LedgerView {
            cumulative_pnl: 0,
            peak_equity: 0,
            window_loss: 0,
            window_start: 0,
            trades_in_window: 0,
        },
        action: SwapAction {
            chain_id: 31337,
            account: addrs.account,
            router: addrs.router,
            token_in_index: 0,
            token_out_index: 1,
            fee: 500,
            amount_in,
            deadline: now.saturating_add(600),
            nonce: 0,
        },
        assets: vec![
            AssetInput {
                token: addrs.weth,
                decimals: 18,
                balance: 10 * 10u128.pow(18),
                prev_head: [0u8; 32],
                points: weth_prices,
            },
            AssetInput {
                token: addrs.usdc,
                decimals: 6,
                balance: 20_000 * 10u128.pow(6),
                prev_head: [0u8; 32],
                points: usdc_prices,
            },
        ],
        expiry: now.saturating_add(600),
    };
    let evaluation = evaluate(&input);
    Scenario {
        name,
        input,
        evaluation,
    }
}

pub fn calm_prices(start: i64, now: u64) -> Vec<PricePoint> {
    (0..8)
        .map(|i| PricePoint {
            price: start + (i as i64) * (start / 2_000),
            conf: 50_000,
            expo: -8,
            publish_time: now.saturating_sub(((7 - i) as u64) * 60),
        })
        .collect()
}

fn jumpy_prices(now: u64) -> Vec<PricePoint> {
    let raw = [
        100_000_000_000i64,
        180_000_000_000,
        90_000_000_000,
        210_000_000_000,
        70_000_000_000,
        230_000_000_000,
        60_000_000_000,
        250_000_000_000,
    ];
    raw.into_iter()
        .enumerate()
        .map(|(i, price)| PricePoint {
            price,
            conf: 50_000,
            expo: -8,
            publish_time: now.saturating_sub(((7 - i) as u64) * 60),
        })
        .collect()
}
