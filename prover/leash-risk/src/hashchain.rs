use sha3::{Digest, Keccak256};

use crate::math::MathError;
use crate::types::PricePoint;

pub fn keccak(data: &[u8]) -> [u8; 32] {
    let mut hasher = Keccak256::new();
    hasher.update(data);
    let out = hasher.finalize();
    let mut word = [0u8; 32];
    word.copy_from_slice(&out);
    word
}

/// `keccak256(abi.encodePacked(prev, int64 price, uint64 conf, int32 expo, uint64 publishTime))`.
pub fn next_head(prev: &[u8; 32], point: &PricePoint) -> Result<[u8; 32], MathError> {
    if point.price <= 0 {
        return Err(MathError::BadPrice);
    }
    let mut buf = [0u8; 60];
    buf[..32].copy_from_slice(prev);
    buf[32..40].copy_from_slice(&point.price.to_be_bytes());
    buf[40..48].copy_from_slice(&point.conf.to_be_bytes());
    buf[48..52].copy_from_slice(&point.expo.to_be_bytes());
    buf[52..60].copy_from_slice(&point.publish_time.to_be_bytes());
    Ok(keccak(&buf))
}

/// Returns `(head_after_first_point, head_after_last_point)`.
pub fn chain(prev: &[u8; 32], points: &[PricePoint]) -> Result<([u8; 32], [u8; 32]), MathError> {
    if points.is_empty() {
        return Err(MathError::BadPrice);
    }
    let mut head = *prev;
    let mut first = [0u8; 32];
    for (i, point) in points.iter().enumerate() {
        head = next_head(&head, point)?;
        if i == 0 {
            first = head;
        }
    }
    Ok((first, head))
}
