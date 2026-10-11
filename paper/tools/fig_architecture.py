"""Fig. 1 of the paper: zkLeash components, split into off-chain and on-chain lanes.

Writes `paper/figures/architecture.png` (3.5 in wide, one IEEE column).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "figures" / "architecture.png"


def box(ax, x, y, w, h, title, sub, fill="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                linewidth=0.8, edgecolor="black", facecolor=fill))
    ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center", fontsize=5.6, weight="bold")
    ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center", fontsize=4.6, linespacing=1.1)


def arrow(ax, a, b, label="", lx=0.0, ly=0.0, style="-|>", rad=0.0):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=6, linewidth=0.7,
                                 color="black", connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=1, shrinkB=1))
    if label:
        mx, my = (a[0] + b[0]) / 2 + lx, (a[1] + b[1]) / 2 + ly
        ax.text(mx, my, label, ha="center", va="center", fontsize=5.0, style="italic",
                bbox=dict(facecolor="white", edgecolor="none", pad=0.4))


def main() -> None:
    plt.rcParams.update({"font.family": "serif"})
    fig, ax = plt.subplots(figsize=(3.5, 2.3))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6.6)
    ax.axis("off")

    ax.add_patch(Rectangle((0.05, 3.55), 9.9, 3.0, facecolor="0.94", edgecolor="0.6",
                           linewidth=0.6, linestyle="--"))
    ax.add_patch(Rectangle((0.05, 0.05), 9.9, 3.2, facecolor="white", edgecolor="0.6",
                           linewidth=0.6))
    ax.text(0.15, 6.38, "Off-chain (untrusted)", fontsize=5.6, va="center", color="0.25")
    ax.text(0.15, 3.07, "On-chain", fontsize=5.6, va="center", color="0.25")

    h = 1.35
    box(ax, 0.25, 4.45, 1.75, h, "LLM agent", "proposes\nan intent")
    box(ax, 2.45, 4.45, 1.75, h, "Tx builder", "intent to\naction")
    box(ax, 4.65, 4.45, 2.45, h, "Prover host", "SP1 guest: risk\nfunction")
    box(ax, 7.75, 4.45, 2.0, h, "Pyth", "signed price\nupdates", fill="0.85")

    box(ax, 0.25, 0.85, 2.15, h, "Validator", "admits only\nexecuteGuarded")
    box(ax, 2.8, 0.85, 2.15, h, "Executor", "verify, re-check,\nswap, read Pyth")
    box(ax, 5.35, 0.85, 1.95, h, "Ledger", "window loss,\npeak equity")
    box(ax, 7.75, 0.85, 2.0, h, "Price log", "hash chain of\nPyth prices")

    arrow(ax, (2.0, 5.12), (2.45, 5.12))
    arrow(ax, (4.2, 5.12), (4.65, 5.12))
    arrow(ax, (5.2, 4.45), (1.6, 2.2), "user op: proof,\npublic values", lx=-0.55, ly=0.55)
    arrow(ax, (2.4, 1.52), (2.8, 1.52))
    arrow(ax, (4.95, 1.35), (5.35, 1.35))
    ax.text(5.15, 0.55, "applyTrade", fontsize=4.6, ha="center", style="italic")
    arrow(ax, (6.3, 2.2), (6.3, 4.45), "ledger\nstate", lx=0.0, ly=-0.25)
    arrow(ax, (8.3, 2.2), (6.9, 4.45), "log heads,\nprices", lx=0.38, ly=-0.25)
    arrow(ax, (9.2, 4.45), (9.2, 2.2), "record", lx=0.0, ly=0.0)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300, bbox_inches="tight", pad_inches=0.02)
    print(OUT)


if __name__ == "__main__":
    main()
