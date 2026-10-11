//! Runs the compiled SP1 guest in the SP1 executor (no proof) and checks that the
//! committed public values are byte-identical to native `evaluate`. Prints a JSON
//! object with the RISC-V cycle count for each window length.

use std::path::PathBuf;

use leash_risk::scenarios::{calm, ScenarioAddrs};
use leash_risk::types::PricePoint;
use sp1_sdk::blocking::{Prover, ProverClient};
use sp1_sdk::{Elf, SP1Stdin};

const NOW: u64 = 1_700_000_000;

fn addr(byte: u8) -> [u8; 20] {
    let mut a = [0u8; 20];
    a[19] = byte;
    a
}

/// `n` points that zigzag by 0.3% around `start`, one minute apart.
fn points(start: i64, n: usize) -> Vec<PricePoint> {
    (0..n)
        .map(|i| PricePoint {
            price: if i % 2 == 0 { start } else { start + start * 3 / 1_000 },
            conf: 50_000,
            expo: -8,
            publish_time: NOW - ((n - 1 - i) as u64) * 60,
        })
        .collect()
}

fn main() {
    let elf_path = std::env::var("ZKLEASH_ELF").map(PathBuf::from).unwrap_or_else(|_| {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../program/elf/zkleash-guest")
    });
    let elf: Elf = std::fs::read(&elf_path).unwrap_or_else(|e| panic!("read {}: {e}", elf_path.display())).into();
    let client = ProverClient::builder().cpu().build();
    let addrs = ScenarioAddrs { account: addr(1), router: addr(2), weth: addr(3), usdc: addr(4) };

    let mut runs = Vec::new();
    for n in [8usize, 16, 32, 64, 128, 256] {
        let mut input = calm(addrs.clone(), 100_000_000_000_000_000, NOW).input;
        input.assets[0].points = points(200_000_000_000, n);
        input.assets[1].points = points(100_000_000, n);
        let native = leash_risk::evaluate(&input);

        let mut stdin = SP1Stdin::new();
        stdin.write(&input);
        let (public_values, report) = client.execute(elf.clone(), stdin).run().expect("sp1 execute");
        let identical = public_values.as_slice() == native.encoded.as_slice();
        assert!(identical, "SP1 public values differ from native evaluate at n = {n}");

        runs.push(serde_json::json!({
            "points_per_asset": n,
            "assets": input.assets.len(),
            "cycles": report.total_instruction_count(),
            "identical": identical,
            "decision": native.public_values.decision,
        }));
    }
    let out = serde_json::json!({
        "source": "cd prover/exec && cargo run --release (SP1 executor, no proof; calm scenario, two assets)",
        "sp1_sdk": "6",
        "runs": runs,
    });
    println!("{}", serde_json::to_string_pretty(&out).expect("json"));
}
