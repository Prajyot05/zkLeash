"""Regenerate `bench/results/gas.json` from the Foundry gas-sample tests.

Runs `forge test --match-test test_gas_ -vv` and parses the `log_named_uint` lines.
Every touched contract is cooled with `vm.cool` before a measurement, so storage
reads are priced as cold, as they would be in a fresh transaction.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bench" / "results" / "gas.json"
GROTH16_VERIFY_GAS = 280_000  # Succinct's published SP1 Groth16 verification cost; not re-measured here


def crossing(samples: dict[int, int], budget: int) -> int:
    """Window length at which the last segment, extended linearly, reaches `budget`."""
    (x0, y0), (x1, y1) = sorted(samples.items())[-2:]
    slope = (y1 - y0) / (x1 - x0)
    for (a, ya), (b, yb) in zip(sorted(samples.items()), sorted(samples.items())[1:]):
        if ya <= budget <= yb:
            return round(a + (budget - ya) * (b - a) / (yb - ya))
    return round(x1 + (budget - y1) / slope)


def main() -> int:
    env = dict(os.environ, PATH=f"{Path.home() / '.foundry' / 'bin'}:{os.environ.get('PATH', '')}")
    proc = subprocess.run(
        ["forge", "test", "--match-test", "test_gas_", "-vv"],
        cwd=ROOT / "contracts",
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        print(proc.stdout, proc.stderr, file=sys.stderr)
        return proc.returncode
    logs = dict((k, int(v)) for k, v in re.findall(r"^\s+(\w+): (\d+)$", proc.stdout, flags=re.M))
    calldata = {int(k.rsplit("_", 1)[1]): v for k, v in logs.items() if re.fullmatch(r"ewma_gas_\d+", k)}
    storage = {int(k.rsplit("_", 1)[1]): v for k, v in logs.items() if re.fullmatch(r"ewma_storage_gas_\d+", k)}
    verifier = logs["stand_in_verifier_gas"]
    first = logs["execute_guarded_first_trade_gas"]
    nxt = logs["execute_guarded_next_trade_gas"]
    out = {
        "source": "python bench/gas_samples.py (forge test --match-test test_gas_ -vv)",
        "note": (
            "Execution gas of one call, contracts cooled with vm.cool, intrinsic and calldata gas excluded. "
            "OnChainEwma.sigma takes unauthenticated calldata; sigmaFromStorage reads one slot per point, "
            "the PriceHistoryLog layout. Groth16 verification is not measured; Succinct publishes roughly 280k gas."
        ),
        "ewma_calldata_gas": {str(k): v for k, v in sorted(calldata.items())},
        "ewma_storage_gas": {str(k): v for k, v in sorted(storage.items())},
        "single_asset_points_to_exceed_280k": {
            "calldata": crossing(calldata, GROTH16_VERIFY_GAS),
            "storage": crossing(storage, GROTH16_VERIFY_GAS),
        },
        "execute_guarded_gas": {
            "first_trade": first,
            "next_trade": nxt,
            "stand_in_verifier": verifier,
            "next_trade_without_verifier": nxt - verifier,
            "next_trade_with_groth16_estimate": nxt - verifier + GROTH16_VERIFY_GAS,
        },
        "price_log_record_gas": logs["price_log_record_gas"],
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
