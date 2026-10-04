"""Permissionless price-log poster.

In production this submits a Pyth pull update to `PriceHistoryLog.record` every few
minutes. Here it prints the call so a keeper can run it, and it can target a local
anvil if `RPC_URL` and `PRICE_LOG` are set and `cast` is on PATH.
"""

import os
import shutil
import subprocess
import sys


def main() -> int:
    rpc = os.environ.get("RPC_URL", "")
    price_log = os.environ.get("PRICE_LOG", "")
    price_id = os.environ.get("PRICE_ID", "")
    if not rpc or not price_log or not price_id:
        print("price log cron: set RPC_URL, PRICE_LOG, and PRICE_ID to broadcast.")
        print("missing env, nothing sent (fail closed: trades will revert on a short history).")
        return 0
    if shutil.which("cast") is None:
        print("cast is not installed; cannot broadcast")
        return 1
    cmd = [
        "cast",
        "send",
        price_log,
        "record(bytes[],bytes32)",
        "[]",
        price_id,
        "--rpc-url",
        rpc,
    ]
    if os.environ.get("PRIVATE_KEY"):
        cmd.extend(["--private-key", os.environ["PRIVATE_KEY"]])
    print(" ".join(cmd[:6]), "...")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
