#!/usr/bin/env bash
# Groth16 proving. Laptops stay on execute/mock mode; this script is the
# Prover Network path used for the Base Sepolia demo.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v cargo-prove >/dev/null 2>&1; then
  echo "cargo-prove is not installed. Develop with:"
  echo "  cargo run -p leash-risk-cli -- check --input <file>"
  echo "Install SP1 from https://docs.succinct.xyz and re-run for a real proof."
  exit 0
fi

export SP1_PROVER="${SP1_PROVER:-network}"
echo "Prover mode: $SP1_PROVER"
(cd program && cargo prove build --output-directory elf --elf-name zkleash-guest)
echo "ELF ready at prover/program/elf/zkleash-guest. Check it with: (cd exec && cargo run --release)"
echo "Then submit with ProverClient::prove(...).groth16() in network mode."
echo "Do this only for the demo and the real-proof confirmation subset."
