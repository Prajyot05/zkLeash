"""Figures for the paper from `bench/results/summary.json`.

Writes `bench/results/salami_curve.png`: cumulative execution loss against the
number of legs for a stateless guard (B4), a daily notional cap (B5), and zkLeash.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"


def _series(curve: list[float], n: int) -> list[float]:
    padded = [0.0] + list(curve)
    if len(padded) < n:
        padded += [padded[-1]] * (n - len(padded))
    return padded[:n]


def salami_curve(summary: dict, out: Path) -> None:
    curves = summary["salami_curves"]
    plt.rcParams.update({"font.family": "serif", "font.size": 8})
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 1.9), constrained_layout=True)
    panels = (
        ("small_leg", "Small legs, 1% extracted"),
        ("realistic", "Large legs, 1% extracted"),
    )
    for ax, (name, title) in zip(axes, panels):
        c = curves[name]
        n = max(len(c["B4_stateless"]), len(c["B5_daily_notional"]), len(c["zkLeash"])) + 1
        ax.plot(_series(c["B4_stateless"], n), color="0.45", linestyle="--", linewidth=1.1, label="Stateless (B4)")
        ax.plot(_series(c["B5_daily_notional"], n), color="0.15", linestyle="-.", linewidth=1.1, label="Daily cap (B5)")
        ax.plot(_series(c["zkLeash"], n), color="black", linewidth=1.4, label="zkLeash")
        ax.axhline(c["cap_usd"], color="black", linewidth=0.6, linestyle=":")
        ax.set_title(title, fontsize=7.5)
        ax.set_xlabel("Legs attempted")
        ax.set_xlim(0, n - 1)
        top = max(_series(c["B4_stateless"], n) + [c["cap_usd"]])
        ax.set_ylim(0, top * 1.08 if top else 1)
        ax.grid(True, linewidth=0.3, color="0.85")
    axes[0].set_ylabel("Cumulative loss (USD)")
    axes[0].legend(loc="upper left", fontsize=6, frameon=False)
    fig.savefig(out, dpi=300)
    plt.close(fig)


def main() -> int:
    summary = json.loads((RESULTS / "summary.json").read_text())
    out = RESULTS / "salami_curve.png"
    salami_curve(summary, out)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
