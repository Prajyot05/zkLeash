//! SP1 guest entry. The RISC-V program reads a `GuestInput`, runs `evaluate`,
//! and commits the abi-encoded public values. The host never gets to choose
//! the decision: it is whatever the guest computes.
#![no_main]

sp1_zkvm::entrypoint!(main);

use leash_risk::evaluate;
use leash_risk::types::GuestInput;

pub fn main() {
    let input = sp1_zkvm::io::read::<GuestInput>();
    let evaluation = evaluate(&input);
    sp1_zkvm::io::commit_slice(&evaluation.encoded);
}
