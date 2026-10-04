//! Future-scope helpers. These are tested, but they are not part of the guest
//! input committed by the MVP executor. See `docs/FUTURE_SCOPE.md`.

use crate::ewma::historical_cvar95;
use crate::hashchain::keccak;
use crate::math::MathError;
use alloc::vec::Vec;

pub fn cvar95_loss(prices: &[i64]) -> Result<u128, MathError> {
    historical_cvar95(prices)
}

/// Commitment to a policy hash plus a secret salt. The salt stays off-chain
/// (or as a private witness) so thresholds are not published next to the account.
pub fn confidential_policy_commitment(policy_commitment: &[u8; 32], salt: &[u8; 32]) -> [u8; 32] {
    let mut buf = Vec::with_capacity(64);
    buf.extend_from_slice(policy_commitment);
    buf.extend_from_slice(salt);
    keccak(&buf)
}
