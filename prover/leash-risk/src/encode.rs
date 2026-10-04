use alloc::vec::Vec;

use crate::hashchain::keccak;
use crate::types::{Policy, PublicValues, SwapAction, MAX_ASSETS, PUBLIC_VALUES_WORDS};

pub fn action_hash(action: &SwapAction, token_in: &[u8; 20], token_out: &[u8; 20]) -> [u8; 32] {
    let mut buf = Vec::with_capacity(9 * 32);
    push_u128(&mut buf, action.chain_id as u128);
    push_addr(&mut buf, &action.account);
    push_addr(&mut buf, &action.router);
    push_addr(&mut buf, token_in);
    push_addr(&mut buf, token_out);
    push_u128(&mut buf, action.fee as u128);
    push_u128(&mut buf, action.amount_in);
    push_u128(&mut buf, action.deadline as u128);
    push_u128(&mut buf, action.nonce as u128);
    keccak(&buf)
}

pub fn policy_commitment(policy: &Policy) -> [u8; 32] {
    let mut buf = Vec::with_capacity(12 * 32);
    push_u128(&mut buf, policy.max_vol_exposure);
    push_u128(&mut buf, policy.max_concentration_bps as u128);
    push_u128(&mut buf, policy.max_drawdown_bps as u128);
    push_u128(&mut buf, policy.max_notional);
    push_u128(&mut buf, policy.max_slippage_bps as u128);
    push_u128(&mut buf, policy.max_window_loss);
    push_u128(&mut buf, policy.window_seconds as u128);
    push_u128(&mut buf, policy.max_trades_per_window as u128);
    push_u128(&mut buf, policy.min_history as u128);
    push_u128(&mut buf, policy.max_price_deviation_bps as u128);
    push_u128(&mut buf, policy.max_price_age as u128);
    push_addr(&mut buf, &policy.quote_token);
    keccak(&buf)
}

pub fn encode_public_values(pv: &PublicValues) -> Vec<u8> {
    let mut buf = Vec::with_capacity(PUBLIC_VALUES_WORDS * 32);
    push_bytes32(&mut buf, &pv.action_hash);
    push_bytes32(&mut buf, &pv.policy_commitment);
    push_u128(&mut buf, pv.asset_count as u128);
    push_u128(&mut buf, pv.expiry as u128);
    push_u128(&mut buf, pv.decision as u128);
    push_i128(&mut buf, pv.cumulative_pnl);
    push_u128(&mut buf, pv.peak_equity);
    push_u128(&mut buf, pv.window_loss);
    push_u128(&mut buf, pv.window_start as u128);
    push_u128(&mut buf, pv.trades_in_window as u128);
    push_u128(&mut buf, pv.vol_exposure);
    push_u128(&mut buf, pv.var99);
    for i in 0..MAX_ASSETS {
        push_bytes32(&mut buf, &pv.head_start[i]);
    }
    for i in 0..MAX_ASSETS {
        push_bytes32(&mut buf, &pv.head_end[i]);
    }
    for i in 0..MAX_ASSETS {
        push_i128(&mut buf, pv.proven_prices[i] as i128);
    }
    for i in 0..MAX_ASSETS {
        push_u128(&mut buf, pv.sigmas[i]);
    }
    for i in 0..MAX_ASSETS {
        push_u128(&mut buf, pv.balances[i]);
    }
    debug_assert_eq!(buf.len(), PUBLIC_VALUES_WORDS * 32);
    buf
}

fn push_u128(buf: &mut Vec<u8>, v: u128) {
    let mut word = [0u8; 32];
    word[16..].copy_from_slice(&v.to_be_bytes());
    buf.extend_from_slice(&word);
}

fn push_i128(buf: &mut Vec<u8>, v: i128) {
    let mut word = if v < 0 { [0xffu8; 32] } else { [0u8; 32] };
    word[16..].copy_from_slice(&v.to_be_bytes());
    buf.extend_from_slice(&word);
}

fn push_addr(buf: &mut Vec<u8>, addr: &[u8; 20]) {
    let mut word = [0u8; 32];
    word[12..].copy_from_slice(addr);
    buf.extend_from_slice(&word);
}

fn push_bytes32(buf: &mut Vec<u8>, word: &[u8; 32]) {
    buf.extend_from_slice(word);
}
