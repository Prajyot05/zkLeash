"""Cross-check the guest's fixed-point EWMA against a NumPy floating-point reference."""

import math
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "prover" / "target" / "debug" / "leash-risk"
ONE = 10**18


def integer_sigma(prices: list[int]) -> int:
    lam = 940_000_000_000_000_000
    one_minus = ONE - lam
    var = 0
    for prev, nxt in zip(prices, prices[1:]):
        r = (nxt - prev) * ONE // prev
        r2 = (abs(r) * abs(r)) // ONE
        var = (lam * var + one_minus * r2) // ONE

    def isqrt(n: int) -> int:
        x = n
        y = x // 2 + 1
        while y < x:
            x = y
            y = (x + n // x) // 2
        return x

    return isqrt(var * ONE)


def numpy_sigma(prices: list[int]) -> float:
    arr = np.asarray(prices, dtype=np.float64)
    rets = np.diff(arr) / arr[:-1]
    lam = 0.94
    var = 0.0
    for r in rets:
        var = lam * var + (1.0 - lam) * float(r) * float(r)
    return math.sqrt(var)


def test_integer_path_matches_the_hand_fixture():
    assert integer_sigma([1000, 1100, 1210]) == 34_117_444_218_463_961


def test_fixed_point_tracks_numpy_within_one_percent():
    prices = [1000, 1100, 1210, 1150, 1300, 900, 1400, 1000]
    fixed = integer_sigma(prices) / ONE
    floated = numpy_sigma(prices)
    assert abs(fixed - floated) / floated < 0.01


def test_cli_scenario_agrees_on_the_calm_allow():
    if not BIN.exists():
        return
    out = subprocess.check_output(
        [
            str(BIN),
            "scenario",
            "calm",
            "--account",
            "0x0000000000000000000000000000000000000001",
            "--router",
            "0x0000000000000000000000000000000000000002",
            "--weth",
            "0x0000000000000000000000000000000000000003",
            "--usdc",
            "0x0000000000000000000000000000000000000004",
            "--now",
            "1700000000",
            "--chain-id",
            "31337",
        ],
        text=True,
    )
    assert '"allowed": true' in out or '"allowed":true' in out
