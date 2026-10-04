//! Deterministic risk checks for zkLeash.
//!
//! Integer math only (1e18 fixed point). The same functions run in native tests,
//! the host CLI, and the SP1 guest. Nothing in this crate reads the network or
//! the clock: every input is passed in, and every output is a pure function of
//! those inputs.

#![cfg_attr(not(feature = "std"), no_std)]

extern crate alloc;

pub mod encode;
pub mod ewma;
pub mod future;
pub mod hashchain;
pub mod math;
pub mod scenarios;
pub mod types;

use alloc::vec::Vec;

use types::{
    AssetInput, DenyReason, Evaluation, GuestInput, PublicValues, SwapAction, DECISION_ALLOW,
    DECISION_DENY, MAX_ASSETS, Z_VAR99,
};

/// Evaluate one proposed swap. Always returns public values. `decision` is
/// [`DECISION_ALLOW`] only when every check passes; otherwise it is
/// [`DECISION_DENY`] and `reasons` lists why. A deny result is still well-formed
/// so a proof of denial can be produced.
pub fn evaluate(input: &GuestInput) -> Evaluation {
    let mut reasons = Vec::new();
    let mut steps: u64 = 0;
    let n = input.assets.len();

    if n == 0 {
        reasons.push(DenyReason::TooFewAssets);
    }
    if n > MAX_ASSETS {
        reasons.push(DenyReason::TooManyAssets);
    }

    let mut heads_start = [[0u8; 32]; MAX_ASSETS];
    let mut heads_end = [[0u8; 32]; MAX_ASSETS];
    let mut proven_prices = [0i64; MAX_ASSETS];
    let mut sigmas = [0u128; MAX_ASSETS];
    let mut post_balances = [0u128; MAX_ASSETS];
    let mut price_1e18 = [0u128; MAX_ASSETS];
    let mut exposures_pre = [0u128; MAX_ASSETS];
    let mut exposures_post = [0u128; MAX_ASSETS];

    let count = n.min(MAX_ASSETS);
    let min_history = input.policy.min_history.max(2) as usize;

    for i in 0..count {
        let asset = &input.assets[i];
        steps += asset.points.len() as u64;
        if asset.points.len() < min_history {
            reasons.push(DenyReason::ShortHistory);
            continue;
        }
        match hashchain::chain(&asset.prev_head, &asset.points) {
            Ok((start, end)) => {
                heads_start[i] = start;
                heads_end[i] = end;
            }
            Err(_) => reasons.push(DenyReason::BadPrice),
        }
        let last = asset.points.last().expect("length checked");
        proven_prices[i] = last.price;
        match math::price_1e18(last.price, last.expo) {
            Ok(px) => price_1e18[i] = px,
            Err(_) => reasons.push(DenyReason::BadPrice),
        }
        match ewma::ewma_sigma(&prices_of(asset)) {
            Ok(sigma) => sigmas[i] = sigma,
            Err(_) => reasons.push(DenyReason::BadPrice),
        }
        post_balances[i] = asset.balance;
        if price_1e18[i] != 0 {
            if let Ok(exp) = math::exposure(asset.balance, price_1e18[i], asset.decimals) {
                exposures_pre[i] = exp;
            } else {
                reasons.push(DenyReason::Overflow);
            }
        }
    }

    let action = &input.action;
    if count > 0
        && (action.token_in_index as usize) < count
        && (action.token_out_index as usize) < count
    {
        if action.token_in_index == action.token_out_index {
            reasons.push(DenyReason::SameToken);
        }
        let i_in = action.token_in_index as usize;
        let i_out = action.token_out_index as usize;
        if action.amount_in > input.assets[i_in].balance {
            reasons.push(DenyReason::InsufficientBalance);
        } else if price_1e18[i_in] != 0 && price_1e18[i_out] != 0 {
            match math::fair_out(
                action.amount_in,
                input.assets[i_in].decimals,
                price_1e18[i_in],
                input.assets[i_out].decimals,
                price_1e18[i_out],
            ) {
                Ok(fair) => {
                    post_balances[i_in] = input.assets[i_in].balance - action.amount_in;
                    post_balances[i_out] = input.assets[i_out].balance.saturating_add(fair);
                    if let Ok(exp) = math::exposure(post_balances[i_in], price_1e18[i_in], input.assets[i_in].decimals) {
                        exposures_post[i_in] = exp;
                    } else {
                        reasons.push(DenyReason::Overflow);
                    }
                    if let Ok(exp) = math::exposure(post_balances[i_out], price_1e18[i_out], input.assets[i_out].decimals) {
                        exposures_post[i_out] = exp;
                    } else {
                        reasons.push(DenyReason::Overflow);
                    }
                }
                Err(_) => reasons.push(DenyReason::Overflow),
            }
        }
        // Assets that are neither in nor out keep their pre-trade exposure.
        for i in 0..count {
            if i != i_in && i != i_out {
                exposures_post[i] = exposures_pre[i];
            }
        }
    } else if count > 0 {
        reasons.push(DenyReason::SameToken);
    }

    let vol_pre = math::vol_exposure(&exposures_pre[..count], &sigmas[..count]).unwrap_or_else(|_| {
        reasons.push(DenyReason::Overflow);
        0
    });
    let vol_post = math::vol_exposure(&exposures_post[..count], &sigmas[..count]).unwrap_or_else(|_| {
        reasons.push(DenyReason::Overflow);
        0
    });
    let var99 = math::mul_div(vol_post, Z_VAR99, crate::types::ONE).unwrap_or_else(|_| {
        reasons.push(DenyReason::Overflow);
        0
    });

    if vol_post > input.policy.max_vol_exposure {
        reasons.push(DenyReason::VolLimit);
    }

    if let Some(i_in) = (action.token_in_index as usize).checked_rem(MAX_ASSETS) {
        if i_in < count && price_1e18[i_in] != 0 {
            if let Ok(notional) = math::exposure(
                action.amount_in,
                price_1e18[i_in],
                input.assets[i_in].decimals,
            ) {
                if notional > input.policy.max_notional {
                    reasons.push(DenyReason::Notional);
                }
            }
        }
    }

    if let Err(reason) = check_concentration(&input.policy, &exposures_post, count, &input.assets) {
        reasons.push(reason);
    }

    let equity_pre: u128 = exposures_pre[..count].iter().fold(0u128, |a, b| a.saturating_add(*b));
    let peak = if input.ledger.peak_equity == 0 {
        equity_pre
    } else {
        input.ledger.peak_equity
    };
    let drawdown_bps = if peak > equity_pre && peak != 0 {
        (peak - equity_pre).saturating_mul(10_000) / peak
    } else {
        0
    };
    if drawdown_bps > input.policy.max_drawdown_bps as u128 {
        let quote = input.policy.quote_index;
        let selling_into_quote = action.token_out_index == quote;
        let reduces_risk = vol_post <= vol_pre;
        if !selling_into_quote || !reduces_risk {
            reasons.push(DenyReason::Drawdown);
        }
    }

    if input.ledger.window_loss >= input.policy.max_window_loss && input.policy.max_window_loss > 0 {
        reasons.push(DenyReason::WindowLoss);
    }
    if input.ledger.trades_in_window >= input.policy.max_trades_per_window {
        reasons.push(DenyReason::TradeRate);
    }

    if count > 0 {
        let quote_idx = input.policy.quote_index as usize;
        if quote_idx >= count || input.assets[quote_idx].token != input.policy.quote_token {
            reasons.push(DenyReason::BadPrice);
        }
    }

    let action_hash = if count > 0
        && (action.token_in_index as usize) < count
        && (action.token_out_index as usize) < count
    {
        encode::action_hash(
            action,
            &input.assets[action.token_in_index as usize].token,
            &input.assets[action.token_out_index as usize].token,
        )
    } else {
        [0u8; 32]
    };
    let policy_commitment = encode::policy_commitment(&input.policy);

    let decision = if reasons.is_empty() {
        DECISION_ALLOW
    } else {
        DECISION_DENY
    };

    let public_values = PublicValues {
        action_hash,
        policy_commitment,
        asset_count: count as u8,
        expiry: input.expiry,
        decision,
        cumulative_pnl: input.ledger.cumulative_pnl,
        peak_equity: input.ledger.peak_equity,
        window_loss: input.ledger.window_loss,
        window_start: input.ledger.window_start,
        trades_in_window: input.ledger.trades_in_window,
        vol_exposure: vol_post,
        var99,
        head_start: heads_start,
        head_end: heads_end,
        proven_prices,
        sigmas,
        balances: post_balances,
    };
    let encoded = encode::encode_public_values(&public_values);

    Evaluation {
        public_values,
        encoded,
        reasons,
        step_count: steps,
        vol_pre,
        equity_pre,
    }
}

fn prices_of(asset: &AssetInput) -> Vec<i64> {
    asset.points.iter().map(|p| p.price).collect()
}

fn check_concentration(
    policy: &types::Policy,
    exposures_post: &[u128; MAX_ASSETS],
    count: usize,
    assets: &[AssetInput],
) -> Result<(), DenyReason> {
    let total: u128 = exposures_post[..count].iter().fold(0u128, |a, b| a.saturating_add(*b));
    if total == 0 {
        return Err(DenyReason::BadPrice);
    }
    for i in 0..count {
        if assets[i].token == policy.quote_token {
            continue;
        }
        let bps = exposures_post[i].saturating_mul(10_000) / total;
        if bps > policy.max_concentration_bps as u128 {
            return Err(DenyReason::Concentration);
        }
    }
    Ok(())
}

/// Re-export the action hash so the host and the contract fixture share one definition.
pub fn hash_action(action: &SwapAction, token_in: &[u8; 20], token_out: &[u8; 20]) -> [u8; 32] {
    encode::action_hash(action, token_in, token_out)
}

#[cfg(test)]
mod tests;
