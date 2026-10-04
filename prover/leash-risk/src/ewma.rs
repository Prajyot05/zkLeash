use crate::math::{isqrt, wmul, MathError, ONE};
use alloc::vec::Vec;

/// RiskMetrics EWMA variance with lambda = 0.94, then `sigma = sqrt(var)` in 1e18.
///
/// `var` is `E[r^2]` scaled by 1e18, so `sigma_1e18 = isqrt(var * 1e18)`.
/// Needs at least two prices. Returns an error on a non-positive price.
pub fn ewma_sigma(prices: &[i64]) -> Result<u128, MathError> {
    if prices.len() < 2 {
        return Err(MathError::BadPrice);
    }
    let lambda: u128 = 940_000_000_000_000_000;
    let one_minus = ONE - lambda;
    let mut var: u128 = 0;
    for i in 1..prices.len() {
        if prices[i] <= 0 || prices[i - 1] <= 0 {
            return Err(MathError::BadPrice);
        }
        let r = return_1e18(prices[i - 1], prices[i])?;
        let r2 = wmul(r.unsigned_abs(), r.unsigned_abs());
        // r^2 / ONE fits in u128 for any i64 return that itself fits.
        let r2_fp = div_256(r2.0, r2.1, ONE)?;
        let term = wmul(one_minus, r2_fp);
        let decay = wmul(lambda, var);
        let term_fp = div_256(term.0, term.1, ONE)?;
        let decay_fp = div_256(decay.0, decay.1, ONE)?;
        var = decay_fp.checked_add(term_fp).ok_or(MathError::Overflow)?;
    }
    let (hi, lo) = wmul(var, ONE);
    // sigma^2 * 1e18 may be a 256-bit number. Take the integer sqrt of that.
    isqrt_256(hi, lo)
}

fn return_1e18(prev: i64, next: i64) -> Result<i128, MathError> {
    let delta = (next as i128)
        .checked_sub(prev as i128)
        .ok_or(MathError::Overflow)?;
    let numer = delta
        .checked_mul(ONE as i128)
        .ok_or(MathError::Overflow)?;
    Ok(numer / (prev as i128))
}

fn div_256(hi: u128, lo: u128, denom: u128) -> Result<u128, MathError> {
    crate::math::div_256_by_u128(hi, lo, denom)
}

/// Integer square root of a 256-bit value. The result fits in u128.
/// We only need this for `var * 1e18`, which for market-sized returns fits in ~128 bits
/// of the root. The algorithm is Newton on u128 when `hi == 0`, otherwise a binary search
/// over the u128 root.
fn isqrt_256(hi: u128, lo: u128) -> Result<u128, MathError> {
    if hi == 0 {
        return Ok(isqrt(lo));
    }
    // Find the smallest x such that x*x >= n, by binary search, then step down while x*x > n.
    let mut lo_r: u128 = 1 << 64; // since hi != 0, root > 2^64
    let mut hi_r: u128 = u128::MAX;
    while lo_r < hi_r {
        let mid = lo_r + (hi_r - lo_r) / 2;
        match cmp_square(mid, hi, lo) {
            core::cmp::Ordering::Less => lo_r = mid + 1,
            core::cmp::Ordering::Greater => hi_r = mid,
            core::cmp::Ordering::Equal => return Ok(mid),
        }
    }
    // lo_r is the first root whose square is >= n. If it overshoots, take lo_r - 1.
    if cmp_square(lo_r, hi, lo) == core::cmp::Ordering::Greater {
        Ok(lo_r - 1)
    } else {
        Ok(lo_r)
    }
}

fn cmp_square(x: u128, hi: u128, lo: u128) -> core::cmp::Ordering {
    let (sh, sl) = crate::math::wmul(x, x);
    (sh, sl).cmp(&(hi, lo))
}

/// Historical CVaR at 95% (future-scope helper, not used by the guest).
/// Returns the mean of the worst 5% of simple returns, as a positive loss magnitude in 1e18.
/// With fewer than 20 returns the tail is one observation.
pub fn historical_cvar95(prices: &[i64]) -> Result<u128, MathError> {
    if prices.len() < 2 {
        return Err(MathError::BadPrice);
    }
    let mut losses: Vec<i128> = Vec::new();
    for i in 1..prices.len() {
        let r = return_1e18(prices[i - 1], prices[i])?;
        losses.push(-r); // positive number means a loss
    }
    losses.sort_unstable();
    let n = losses.len();
    let tail = core::cmp::max(1, (n * 5) / 100);
    let start = n - tail;
    let mut sum: i128 = 0;
    for loss in losses.iter().skip(start) {
        sum = sum.checked_add(*loss).ok_or(MathError::Overflow)?;
    }
    let mean = sum / tail as i128;
    if mean <= 0 {
        Ok(0)
    } else {
        Ok(mean as u128)
    }
}
