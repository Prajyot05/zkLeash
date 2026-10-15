"""Replay real ETH/USD hourly prices through the guest.

The window is the August 2024 yen-carry unwind. Prices are Pyth Crypto.ETH/USD
hourly bars when that feed answers, otherwise Binance ETHUSDT hourly closes.
Sigma here is per hour, not per minute, so the dollar budget is calibrated from
the calm window rather than copied from the one-minute harness policy.

Writes bench/results/crash_replay.json. This is one case study, not a trial in
the harness rate.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "prover" / "target" / "debug" / "leash-risk"
OUT = Path(__file__).resolve().parent / "results" / "crash_replay.json"

ONE = 10**18
# 2024-07-28 00:00 UTC through 2024-08-07 00:00 UTC.
START = int(datetime(2024, 7, 28, tzinfo=timezone.utc).timestamp())
END = int(datetime(2024, 8, 7, tzinfo=timezone.utc).timestamp())
WINDOW = 48
ACCOUNT = "0x0000000000000000000000000000000000000001"
ROUTER = "0x0000000000000000000000000000000000000002"
WETH = "0x0000000000000000000000000000000000000003"
USDC = "0x0000000000000000000000000000000000000004"


def _curl(url: str) -> bytes:
    proc = subprocess.run(
        ["curl", "-fsSL", "--retry", "2", url],
        check=True,
        capture_output=True,
    )
    return proc.stdout


def fetch_pyth() -> list[tuple[int, float]] | None:
    url = (
        "https://benchmarks.pyth.network/v1/shims/tradingview/history"
        f"?symbol=Crypto.ETH/USD&resolution=60&from={START}&to={END}"
    )
    try:
        payload = json.loads(_curl(url))
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print("pyth unavailable:", exc)
        return None
    if payload.get("s") != "ok":
        print("pyth status", payload.get("s"))
        return None
    return list(zip(payload["t"], payload["c"]))


def fetch_binance() -> list[tuple[int, float]]:
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol=ETHUSDT&interval=1h&startTime={START * 1000}&endTime={END * 1000}&limit=1000"
    )
    rows = json.loads(_curl(url))
    return [(int(row[0]) // 1000, float(row[4])) for row in rows]


def fetch() -> tuple[str, list[tuple[int, float]]]:
    pyth = fetch_pyth()
    if pyth and len(pyth) >= WINDOW + 24:
        return "Pyth Crypto.ETH/USD hourly, benchmarks.pyth.network tradingview shim", pyth
    return "Binance ETHUSDT hourly closes, api.binance.com", fetch_binance()


def slice_ending(bars: list[tuple[int, float]], end_ts: int) -> list[tuple[int, float]]:
    eligible = [bar for bar in bars if bar[0] <= end_ts]
    return eligible[-WINDOW:]


def guest_input(bars: list[tuple[int, float]], amount_usdc: int, token_in: int, max_vol: int) -> dict:
    last_ts = bars[-1][0]
    weth_px = int(round(bars[-1][1] * 1e8))
    weth_bal = int(5 * 1e18)
    usdc_bal = int(15_000 * 1e6)
    points = [
        {"price": str(int(round(px * 1e8))), "conf": "50000", "expo": -8, "publish_time": str(ts)}
        for ts, px in bars
    ]
    usdc_points = [
        {"price": "100000000", "conf": "10000", "expo": -8, "publish_time": str(ts)} for ts, _ in bars
    ]
    return {
        "policy": {
            "max_vol_exposure": str(max_vol),
            "max_concentration_bps": "8000",
            "max_drawdown_bps": "9000",
            "max_notional": str(30_000 * ONE),
            "max_slippage_bps": "100",
            "max_window_loss": str(400 * ONE),
            "window_seconds": "86400",
            "max_trades_per_window": "20",
            "min_history": "8",
            "max_price_deviation_bps": "50",
            "max_price_age": "172800",
            "quote_token": USDC,
            "quote_index": "1",
        },
        "ledger": {k: "0" for k in ("cumulative_pnl", "peak_equity", "window_loss", "window_start", "trades_in_window")},
        "action": {
            "chain_id": "31337",
            "account": ACCOUNT,
            "router": ROUTER,
            "token_in_index": str(token_in),
            "token_out_index": str(1 - token_in),
            "fee": "500",
            "amount_in": str(amount_usdc if token_in == 1 else int(1e18)),
            "deadline": str(last_ts + 3600),
            "nonce": "0",
        },
        "assets": [
            {"token": WETH, "decimals": "18", "balance": str(weth_bal), "prev_head": "0x" + "00" * 32, "points": points},
            {"token": USDC, "decimals": "6", "balance": str(usdc_bal), "prev_head": "0x" + "00" * 32, "points": usdc_points},
        ],
        "expiry": str(last_ts + 3600),
        "_spot": weth_px,
    }


def run(inputs: list[dict]) -> list[dict]:
    clean = []
    for item in inputs:
        item = dict(item)
        item.pop("_spot", None)
        clean.append(item)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(clean, handle)
        path = handle.name
    try:
        proc = subprocess.run([str(BIN), "check", "--input", path], check=True, capture_output=True, text=True)
    finally:
        Path(path).unlink(missing_ok=True)
    return json.loads(proc.stdout)


def describe(name: str, bars: list[tuple[int, float]], decision: dict) -> dict:
    start, end = bars[0], bars[-1]
    return {
        "name": name,
        "start": datetime.fromtimestamp(start[0], timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "end": datetime.fromtimestamp(end[0], timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "eth_start": round(start[1], 2),
        "eth_end": round(end[1], 2),
        "return": round(end[1] / start[1] - 1, 4),
        "sigma": int(decision["sigmas"][0]) / ONE,
        "vol_exposure_usd": int(decision["vol_exposure"]) / ONE,
        "allowed": decision["allowed"],
        "reasons": decision["reasons"],
    }


def main() -> int:
    if not BIN.exists():
        print(f"missing {BIN}", flush=True)
        return 1
    source, bars = fetch()
    if len(bars) < WINDOW + 24:
        print(f"only {len(bars)} bars from {source}", flush=True)
        return 1
    # Calm anchor: 48 hours ending 2024-08-01 00:00 UTC. Crash anchor: the hour
    # with the lowest close on 2024-08-05, which is the carry-unwind day.
    calm_end = int(datetime(2024, 8, 1, tzinfo=timezone.utc).timestamp())
    crash_day = [bar for bar in bars if datetime.fromtimestamp(bar[0], timezone.utc).date().isoformat() == "2024-08-05"]
    if not crash_day:
        print("no bars on 2024-08-05", flush=True)
        return 1
    crash_end = min(crash_day, key=lambda bar: bar[1])[0]
    calm = slice_ending(bars, calm_end)
    crash = slice_ending(bars, crash_end)

    # Probe the calm buy with a wide budget so the exposure number is meaningful,
    # then set the hourly budget just above that calm exposure.
    probe = guest_input(calm, 2_000 * 10**6, 1, 10**9 * ONE)
    probed = run([probe])[0]
    calm_v = int(probed["vol_exposure"])
    budget = int(calm_v * 1.5)
    cases = [
        ("calm_buy", calm, 2_000 * 10**6, 1),
        ("crash_buy", crash, 2_000 * 10**6, 1),
        ("crash_sell", crash, 10**18, 0),
    ]
    decisions = run([guest_input(b, amount, token, budget) for _, b, amount, token in cases])
    report = {
        "source": source,
        "cadence": "1 hour",
        "window_hours": WINDOW,
        "budget_rule": "1.5 times the calm window's post-trade vol exposure on a $2,000 ETH buy",
        "max_vol_exposure_usd": round(budget / ONE, 2),
        "calm_probe_vol_exposure_usd": round(calm_v / ONE, 2),
        "book": "5 ETH and 15,000 USDC",
        "drawdown_cap_bps": 9000,
        "harness_drawdown_cap_bps": 3000,
        "max_price_age_seconds": 172800,
        "harness_max_price_age_seconds": 3600,
        "usdc": "a flat $1",
        "cases": [describe(name, b, decision) for (name, b, _, _), decision in zip(cases, decisions)],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
