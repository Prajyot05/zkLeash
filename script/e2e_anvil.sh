#!/usr/bin/env bash
# Boot the stack on a local Anvil. This is the integration check that does not
# need Base Sepolia ETH. Real Groth16 proofs are a separate step: see prover/script/prove.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PATH:$HOME/.foundry/bin"
cd "$ROOT/contracts"

if ! command -v anvil >/dev/null 2>&1; then
  echo "anvil is not on PATH. Install Foundry: https://book.getfoundry.sh/getting-started/installation"
  exit 1
fi

anvil --port 8545 --silent &
ANVIL_PID=$!
trap 'kill $ANVIL_PID 2>/dev/null || true' EXIT
sleep 1

forge script script/Deploy.s.sol --rpc-url http://127.0.0.1:8545 --broadcast
echo "Anvil deployment finished. The node is still up until this script exits."
