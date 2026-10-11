use crate::encode::{action_hash, encode_public_values, policy_commitment};
use crate::ewma::{ewma_sigma, historical_cvar95};
use crate::future::confidential_policy_commitment;
use crate::hashchain::{chain, next_head};
use crate::math::{fair_out, price_1e18};
use crate::types::*;
use crate::evaluate;

fn point(price: i64, t: u64) -> PricePoint {
    PricePoint {
        price,
        conf: 100,
        expo: -8,
        publish_time: t,
    }
}

fn addr(byte: u8) -> [u8; 20] {
    let mut a = [0u8; 20];
    a[19] = byte;
    a
}

fn calm_points(start: i64, n: usize) -> Vec<PricePoint> {
    (0..n)
        .map(|i| point(start + i as i64, (i as u64) + 1))
        .collect()
}

fn asset(token: [u8; 20], decimals: u8, balance: u128, points: Vec<PricePoint>) -> AssetInput {
    AssetInput {
        token,
        decimals,
        balance,
        prev_head: [0u8; 32],
        points,
    }
}

fn policy(quote: [u8; 20]) -> Policy {
    Policy {
        max_vol_exposure: 50_000 * ONE,
        max_concentration_bps: 7_000,
        max_drawdown_bps: 2_000,
        max_notional: 20_000 * ONE,
        max_slippage_bps: 100,
        max_window_loss: 1_000 * ONE,
        window_seconds: 86_400,
        max_trades_per_window: 10,
        min_history: 8,
        max_price_deviation_bps: 50,
        max_price_age: 600,
        quote_token: quote,
        quote_index: 1,
    }
}

fn sample_input(amount_in: u128, weth_prices: Vec<PricePoint>) -> GuestInput {
    let weth = addr(1);
    let usdc = addr(2);
    let mut p = policy(usdc);
    p.quote_index = 1;
    GuestInput {
        policy: p,
        ledger: LedgerView {
            cumulative_pnl: 0,
            peak_equity: 0,
            window_loss: 0,
            window_start: 1,
            trades_in_window: 0,
        },
        action: SwapAction {
            chain_id: 31337,
            account: addr(9),
            router: addr(8),
            token_in_index: 0,
            token_out_index: 1,
            fee: 500,
            amount_in,
            deadline: 1_900_000_000,
            nonce: 0,
        },
        assets: vec![
            asset(weth, 18, 10 * 10u128.pow(18), weth_prices),
            asset(usdc, 6, 20_000 * 10u128.pow(6), calm_points(100_000_000, 8)),
        ],
        expiry: 1_900_000_000,
    }
}

#[test]
fn widening_mul_matches_small_products() {
    let (hi, lo) = crate::math::wmul(3, 5);
    assert_eq!(hi, 0);
    assert_eq!(lo, 15);
    let (hi, lo) = crate::math::wmul(1u128 << 100, 1u128 << 100);
    assert_eq!(lo, 0);
    assert_eq!(hi, 1u128 << 72); // 2^200 = 2^72 * 2^128
}

#[test]
fn ewma_matches_hand_calculation() {
    // Two successive +10% moves. See the integer trace in the crate docs.
    let sigma = ewma_sigma(&[1000, 1100, 1210]).unwrap();
    assert_eq!(sigma, 34_117_444_218_463_961);
}

#[test]
fn ewma_increases_with_jumpier_prices() {
    let calm = ewma_sigma(&vec![1000i64; 8]).unwrap_or(0);
    let jumpy = ewma_sigma(&[1000, 1100, 900, 1200, 800, 1300, 700, 1400]).unwrap();
    assert!(jumpy > calm);
}

#[test]
fn hash_chain_is_deterministic_and_sensitive() {
    let points = calm_points(200_000_000_000, 4);
    let (start, end) = chain(&[0u8; 32], &points).unwrap();
    let (start2, end2) = chain(&[0u8; 32], &points).unwrap();
    assert_eq!(start, start2);
    assert_eq!(end, end2);
    assert_ne!(start, end);
    let mut tampered = points.clone();
    tampered[2].price += 1;
    let (_, end3) = chain(&[0u8; 32], &tampered).unwrap();
    assert_ne!(end, end3);
    let again = next_head(&[0u8; 32], &points[0]).unwrap();
    assert_eq!(again, start);
}

#[test]
fn fair_out_one_weth_at_2000() {
    let price_weth = price_1e18(200_000_000_000, -8).unwrap();
    let price_usdc = price_1e18(100_000_000, -8).unwrap();
    assert_eq!(price_weth, 2_000 * ONE);
    assert_eq!(price_usdc, ONE);
    let out = fair_out(10u128.pow(18), 18, price_weth, 6, price_usdc).unwrap();
    assert_eq!(out, 2_000 * 10u128.pow(6));
}

#[test]
fn calm_rebalance_is_allowed() {
    // 2000.00 with expo -8, drifting by 1e8 (one dollar) so volatility stays tiny.
    let prices = (0..8)
        .map(|i| point(200_000_000_000 + (i as i64) * 100_000_000, i + 1))
        .collect();
    let input = sample_input(10u128.pow(17), prices); // 0.1 WETH
    let ev = evaluate(&input);
    assert!(
        ev.reasons.is_empty(),
        "unexpected deny: {:?}",
        ev.reasons.iter().map(|r| r.as_str()).collect::<Vec<_>>()
    );
    assert_eq!(ev.public_values.decision, DECISION_ALLOW);
    assert_eq!(ev.encoded.len(), PUBLIC_VALUES_WORDS * 32);
    assert_eq!(encode_public_values(&ev.public_values).len(), ev.encoded.len());
}

#[test]
fn all_in_to_volatile_asset_is_denied() {
    let prices = vec![
        point(100_000_000_000, 1),
        point(180_000_000_000, 2),
        point(90_000_000_000, 3),
        point(200_000_000_000, 4),
        point(70_000_000_000, 5),
        point(220_000_000_000, 6),
        point(60_000_000_000, 7),
        point(250_000_000_000, 8),
    ];
    // Buy WETH with the entire USDC stack: token in is USDC (index 1).
    let mut input = sample_input(0, prices);
    input.action.token_in_index = 1;
    input.action.token_out_index = 0;
    input.action.amount_in = 20_000 * 10u128.pow(6);
    let ev = evaluate(&input);
    assert!(
        ev.reasons.iter().any(|r| *r == DenyReason::VolLimit || *r == DenyReason::Concentration),
        "expected a risk deny, got {:?}",
        ev.reasons
    );
    assert_eq!(ev.public_values.decision, DECISION_DENY);
}

fn jumpy_points() -> Vec<PricePoint> {
    [100_000_000_000i64, 180_000_000_000, 90_000_000_000, 200_000_000_000, 70_000_000_000, 220_000_000_000, 60_000_000_000, 250_000_000_000]
        .iter()
        .enumerate()
        .map(|(i, p)| point(*p, i as u64 + 1))
        .collect()
}

#[test]
fn selling_into_quote_over_budget_is_allowed_and_buying_is_not() {
    // V is about $25k on the jumpy history; the budget is $40.
    let mut sell = sample_input(5 * 10u128.pow(18), jumpy_points());
    sell.policy.max_vol_exposure = 40 * ONE;
    sell.ledger.peak_equity = 200_000 * ONE; // deep drawdown as well
    let ev = evaluate(&sell);
    assert!(ev.reasons.is_empty(), "de-risking was denied: {:?}", ev.reasons);
    assert!(ev.public_values.vol_exposure > sell.policy.max_vol_exposure);

    let mut buy = sell.clone();
    buy.action.token_in_index = 1;
    buy.action.token_out_index = 0;
    buy.action.amount_in = 1_000 * 10u128.pow(6);
    let ev = evaluate(&buy);
    assert!(ev.reasons.contains(&DenyReason::VolLimit), "got {:?}", ev.reasons);
    assert!(ev.reasons.contains(&DenyReason::Drawdown), "got {:?}", ev.reasons);
}

#[test]
fn risk_reducing_exemption_needs_the_quote_asset_as_output() {
    let mut input = sample_input(5 * 10u128.pow(18), jumpy_points());
    input.policy.max_vol_exposure = 40 * ONE;
    // Make WETH the quote asset, so selling WETH for USDC is no longer into the quote.
    input.policy.quote_token = input.assets[0].token;
    input.policy.quote_index = 0;
    let ev = evaluate(&input);
    assert!(ev.reasons.contains(&DenyReason::VolLimit), "got {:?}", ev.reasons);
}

#[test]
fn repeated_publish_time_is_denied() {
    // Padding a jumpy history with copies of the last point drags sigma down.
    let mut padded = jumpy_points();
    let last = padded.last().unwrap().clone();
    padded.extend(core::iter::repeat(last).take(60));
    let padded_sigma = ewma_sigma(&padded.iter().map(|p| p.price).collect::<Vec<_>>()).unwrap();
    let honest_sigma = ewma_sigma(&jumpy_points().iter().map(|p| p.price).collect::<Vec<_>>()).unwrap();
    assert!(padded_sigma * 5 < honest_sigma, "padding should cut sigma by more than 5x");

    let ev = evaluate(&sample_input(10u128.pow(17), padded));
    assert!(ev.reasons.contains(&DenyReason::NonIncreasingTime), "got {:?}", ev.reasons);
}

#[test]
fn short_history_fails_closed() {
    let input = sample_input(1, calm_points(200_000_000_000, 3));
    let ev = evaluate(&input);
    assert!(ev.reasons.iter().any(|r| *r == DenyReason::ShortHistory));
}

#[test]
fn policy_and_action_hashes_are_32_bytes() {
    let input = sample_input(1, calm_points(200_000_000_000, 8));
    let h = action_hash(
        &input.action,
        &input.assets[0].token,
        &input.assets[1].token,
    );
    let p = policy_commitment(&input.policy);
    assert_ne!(h, [0u8; 32]);
    assert_ne!(p, [0u8; 32]);
    assert_ne!(h, p);
}

#[test]
fn cvar_and_confidential_commitment_future_helpers() {
    let prices = [100, 90, 110, 80, 120, 70, 130, 60, 140, 50, 150, 40, 160, 30, 170, 20, 180, 10, 190, 5, 200];
    let cvar = historical_cvar95(&prices).unwrap();
    assert!(cvar > 0);
    let salt = [7u8; 32];
    let policy = [9u8; 32];
    let c1 = confidential_policy_commitment(&policy, &salt);
    let c2 = confidential_policy_commitment(&policy, &[8u8; 32]);
    assert_ne!(c1, c2);
}
