"""Figures for the paper from `bench/results/summary.json`.

Writes `bench/results/salami_curve.png`: cumulative execution loss against the
number of salami legs, for a stateless guard (B4) and for zkLeash, in the toy and
realistic settings that `leashbench.salami_curves` produces.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"


def salami_curve(summary: dict, out: Path) -> None:
    curves = summary["salami_curves"]
    plt.rcParams.update({"font.family": "serif", "font.size": 8})
    fig, axes = plt.subplots(1, 2, figsize=(3.5, 1.9), constrained_layout=True)
    for ax, name in zip(axes, ("toy", "realistic")):
        c = curves[name]
        b4 = [0.0] + c["B4_stateless"]
        zk = [0.0] + c["zkLeash"]
        # Legs zkLeash refuses add nothing, so its curve stays flat to the last attempted leg.
        zk += [zk[-1]] * (len(b4) - len(zk))
        ax.plot(range(len(b4)), b4, color="0.45", linestyle="--", linewidth=1.1, label="Stateless (B4)")
        ax.plot(range(len(zk)), zk, color="black", linewidth=1.4, label="zkLeash")
        ax.axhline(c["cap_usd"], color="black", linewidth=0.6, linestyle=":")
        ax.set_title(f"\\${c['leg_usd']:,.0f} legs, \\${c['cap_usd']:,.0f} cap", fontsize=7.5)
        ax.set_xlabel("Legs attempted")
        ax.set_xlim(0, len(b4) - 1)
        ax.set_ylim(0, max(b4) * 1.05)
        ax.grid(True, linewidth=0.3, color="0.85")
    axes[0].set_ylabel("Cumulative loss (USD)")
    axes[0].legend(loc="upper left", fontsize=6.5, frameon=False)
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
