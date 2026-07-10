"""Renders benchmarks/results/results.json (produced by run_benchmarks.py)
into benchmarks/results/benchmark_chart.png for the project report.

Two separate charts, not one dual-axis chart: instruction count and
execution time are different measures on different scales, and mixing
them on one plot with two y-axes is the most common charting mistake.
Execution time uses a log scale since it spans four orders of magnitude
across benchmarks (constant_showcase has no loop; loop_redundant runs 2M
iterations) - a linear scale would make the faster bars invisible.
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

RESULTS_PATH = Path(__file__).parent / "results" / "results.json"
OUT_PATH = Path(__file__).parent / "results" / "benchmark_chart.png"

# validated categorical pair (dataviz skill, references/palette.md, slots 1-2)
COLOR_BEFORE = "#2a78d6"  # blue
COLOR_AFTER = "#1baf7a"   # aqua
INK_PRIMARY = "#0b0b0b"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
SURFACE = "#fcfcfb"


def _style_axis(ax):
    ax.set_facecolor(SURFACE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRIDLINE)
    ax.spines["bottom"].set_color(GRIDLINE)
    ax.tick_params(colors=INK_MUTED, labelsize=9)
    ax.yaxis.grid(True, color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def _grouped_bars(ax, names, before, after, ylabel, log_scale=False, value_fmt="{:.0f}"):
    x = range(len(names))
    width = 0.35
    bars_before = ax.bar(
        [i - width / 2 for i in x], before, width,
        label="Before optimization", color=COLOR_BEFORE, zorder=3,
    )
    bars_after = ax.bar(
        [i + width / 2 for i in x], after, width,
        label="After -O2 (all passes)", color=COLOR_AFTER, zorder=3,
    )

    if log_scale:
        ax.set_yscale("log")

    for bars in (bars_before, bars_after):
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                value_fmt.format(height),
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha="center", va="bottom", fontsize=7.5, color=INK_PRIMARY,
            )

    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=15, ha="right", fontsize=9, color=INK_PRIMARY)
    ax.set_ylabel(ylabel, fontsize=9, color=INK_MUTED)
    _style_axis(ax)


def main():
    if not RESULTS_PATH.exists():
        print(f"error: {RESULTS_PATH} not found - run run_benchmarks.py first", file=sys.stderr)
        sys.exit(1)

    results = json.loads(RESULTS_PATH.read_text())
    names = [r["name"] for r in results]

    fig, (ax_instr, ax_time) = plt.subplots(1, 2, figsize=(12, 5.5))
    fig.patch.set_facecolor(SURFACE)

    _grouped_bars(
        ax_instr, names,
        [r["instructions_before"] for r in results],
        [r["instructions_after"] for r in results],
        ylabel="TAC instructions",
    )
    ax_instr.set_title("Instruction count: before vs. after", fontsize=11, color=INK_PRIMARY, loc="left")

    _grouped_bars(
        ax_time, names,
        [r["time_before_ms"] for r in results],
        [r["time_after_ms"] for r in results],
        ylabel="Execution time, ms (log scale)",
        log_scale=True,
        value_fmt="{:.3f}",
    )
    ax_time.set_title("Execution time: before vs. after", fontsize=11, color=INK_PRIMARY, loc="left")

    handles, labels = ax_instr.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.99), ncol=2, frameon=False, fontsize=9)

    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(OUT_PATH, dpi=150, facecolor=SURFACE)
    print(f"Chart written to {OUT_PATH}")


if __name__ == "__main__":
    main()
