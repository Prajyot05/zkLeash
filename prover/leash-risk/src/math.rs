pub use crate::types::ONE;

/// `(high, low)` limbs of a full 256-bit product. Implemented by hand because
/// `u128::widening_mul` is still unstable on the toolchain this repo targets.
pub fn wmul(a: u128, b: u128) -> (u128, u128) {
    let a0 = (a as u64) as u128;
    let a1 = a >> 64;
    let b0 = (b as u64) as u128;
    let b1 = b >> 64;
    let ll = a0 * b0;
    let lh = a0 * b1;
    let hl = a1 * b0;
    let hh = a1 * b1;
    let mid = (ll >> 64) + (lh & 0xFFFF_FFFF_FFFF_FFFF) + (hl & 0xFFFF_FFFF_FFFF_FFFF);
    let lo = (ll & 0xFFFF_FFFF_FFFF_FFFF) | ((mid & 0xFFFF_FFFF_FFFF_FFFF) << 64);
    let hi = hh + (lh >> 64) + (hl >> 64) + (mid >> 64);
    (hi, lo)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MathError {
    DivZero,
    Overflow,
    BadPrice,
    BadExpo,
}

pub fn price_1e18(price: i64, expo: i32) -> Result<u128, MathError> {
    if price <= 0 {
        return Err(MathError::BadPrice);
    }
    if !(-18..=18).contains(&expo) {
        return Err(MathError::BadExpo);
    }
    let scale = 18 + expo;
    let factor = 10u128
        .checked_pow(scale as u32)
        .ok_or(MathError::Overflow)?;
    (price as u128)
        .checked_mul(factor)
        .ok_or(MathError::Overflow)
}

pub fn exposure(balance: u128, price_1e18: u128, decimals: u8) -> Result<u128, MathError> {
    if decimals > 36 {
        return Err(MathError::BadExpo);
    }
    let scale = 10u128
        .checked_pow(decimals as u32)
        .ok_or(MathError::Overflow)?;
    mul_div(balance, price_1e18, scale)
}

/// `amount_out = amount_in * price_in * 10^dec_out / (price_out * 10^dec_in)`, truncating.
pub fn fair_out(
    amount_in: u128,
    dec_in: u8,
    price_in: u128,
    dec_out: u8,
    price_out: u128,
) -> Result<u128, MathError> {
    if price_out == 0 || dec_in > 36 || dec_out > 36 {
        return Err(MathError::DivZero);
    }
    let scale_out = 10u128.checked_pow(dec_out as u32).ok_or(MathError::Overflow)?;
    let scale_in = 10u128.checked_pow(dec_in as u32).ok_or(MathError::Overflow)?;
    let denom = price_out.checked_mul(scale_in).ok_or(MathError::Overflow)?;
    let (hi, lo) = wmul(amount_in, price_in);
    let (hi2, lo2) = mul_256_by_u128(hi, lo, scale_out)?;
    div_256_by_u128(hi2, lo2, denom)
}

pub fn vol_exposure(exposures: &[u128], sigmas: &[u128]) -> Result<u128, MathError> {
    let mut sum = 0u128;
    for (exp, sigma) in exposures.iter().zip(sigmas.iter()) {
        let term = mul_div(*exp, *sigma, ONE)?;
        sum = sum.checked_add(term).ok_or(MathError::Overflow)?;
    }
    Ok(sum)
}

pub fn mul_div(a: u128, b: u128, denom: u128) -> Result<u128, MathError> {
    if denom == 0 {
        return Err(MathError::DivZero);
    }
    let (hi, lo) = wmul(a, b);
    div_256_by_u128(hi, lo, denom)
}

fn mul_256_by_u128(hi: u128, lo: u128, m: u128) -> Result<(u128, u128), MathError> {
    let (lo_hi, lo_lo) = wmul(lo, m);
    let (hi_hi, hi_lo) = wmul(hi, m);
    if hi_hi != 0 {
        return Err(MathError::Overflow);
    }
    let (mid, carry) = hi_lo.overflowing_add(lo_hi);
    if carry {
        return Err(MathError::Overflow);
    }
    Ok((mid, lo_lo))
}

/// Divide a 256-bit number `(hi << 128) | lo` by `denom`. Errors if the quotient does not fit in u128.
pub fn div_256_by_u128(hi: u128, lo: u128, denom: u128) -> Result<u128, MathError> {
    if denom == 0 {
        return Err(MathError::DivZero);
    }
    if hi == 0 {
        return Ok(lo / denom);
    }
    if hi >= denom {
        return Err(MathError::Overflow);
    }
    let mut r = hi;
    let mut q = 0u128;
    for i in (0..128).rev() {
        let bit = (lo >> i) & 1;
        let (shifted, overflow) = r.overflowing_shl(1);
        if overflow {
            return Err(MathError::Overflow);
        }
        r = shifted | bit;
        if r >= denom {
            r -= denom;
            q |= 1u128 << i;
        }
    }
    Ok(q)
}

pub fn isqrt(n: u128) -> u128 {
    if n == 0 {
        return 0;
    }
    let mut x = n;
    let mut y = x / 2 + 1;
    while y < x {
        x = y;
        y = (x + n / x) / 2;
    }
    x
}
