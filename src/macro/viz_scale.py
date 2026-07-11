"""Slide 2 exhibit (right panel): the "hidden in plain sight" scale graphic —
proportional-area bars of outstanding by market, CLO in accent — plus a
companion 10y growth-rate dot plot.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK, INK_MUTED, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.macro.viz_scale")

COMPARISON_PATH = config.FINAL_DIR / "macro_market_size_comparison.parquet"
GROWTH_PATH = config.FINAL_DIR / "macro_market_size_growth_10y.parquet"


def viz_market_size_bars():
    apply_theme()
    df = read_parquet(COMPARISON_PATH)
    if df.empty:
        logger.warning("no market-size comparison data; skipping viz_market_size_bars")
        return None
    df = df.sort_values("value_usd_millions", ascending=True).reset_index(drop=True)
    trillions = df["value_usd_millions"] / 1e6

    fig, ax = plt.subplots(figsize=(9.5, 5))
    colors = [ACCENT if m.startswith("CLO") else WARM_GRAY[1] for m in df["market"]]
    bars = ax.barh(df["market"], trillions, color=colors, height=0.62)

    for bar, (_, row) in zip(bars, df.iterrows()):
        label = f"${row['value_usd_millions']/1e6:.1f}T"
        if row["to_verify"]:
            label += f"  (as of {row['as_of']}, TO-VERIFY)"
        elif row["market"] != df.iloc[-1]["market"]:
            ratio = row["x_times_clo"]
            label += f"  ({ratio:.0f}x the CLO figure above)"
        ax.annotate(label, xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2), xytext=(6, 0),
                    textcoords="offset points", va="center", fontsize=9, color=INK)

    ax.set_xlim(0, trillions.max() * 1.32)
    ax.set_xlabel("Outstanding ($ trillions)")
    ax.tick_params(axis="y", labelsize=10)
    fig.subplots_adjust(left=0.26)
    png, svg = save_figure(
        fig, "viz_market_size_bars",
        headline="The only free, dated CLO estimate is $340 billion — and it is six years stale.",
        subtitle="Amount outstanding by market. CLO figure is U.S.-investor-held CLO securities as of Dec 2018 (the most recent free, "
                 "machine-readable estimate found — see notes); every other bar is current, so the true gap today is smaller than these ratios show.",
        source="clo-atlas, from FRED (Treasury/Fed series) and a Federal Reserve FEDS Note (CLO figure, TO-VERIFY)",
        notes="CLO/comparator vintages differ (Dec 2018 vs. current); ratios are therefore conservative — every other market has also grown since 2018.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_growth_10y_dotplot():
    apply_theme()
    df = read_parquet(GROWTH_PATH)
    if df.empty:
        logger.warning("no 10y growth data; skipping viz_growth_10y_dotplot")
        return None
    df = df.sort_values("cagr_10y", ascending=True, na_position="first").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(8.5, 4))
    for i, row in df.iterrows():
        color = ACCENT if row["market"].startswith("CLO") else WARM_GRAY[1]
        if pd.isna(row["cagr_10y"]):
            ax.annotate("not computable\n(single dated snapshot)", xy=(0, i), fontsize=8.5, color=INK_MUTED,
                        va="center", ha="left", style="italic")
            continue
        ax.scatter([row["cagr_10y"] * 100], [i], s=140, color=color, zorder=3)
        ax.annotate(f"{row['cagr_10y']*100:.1f}%/yr", xy=(row["cagr_10y"] * 100, i), xytext=(10, 0),
                    textcoords="offset points", va="center", fontsize=9.5, color=INK)

    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["market"], fontsize=9.5)
    ax.axvline(0, color=INK_MUTED, linewidth=0.8)
    ax.set_xlabel("10-year CAGR of amount outstanding")
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    fig.subplots_adjust(left=0.26)
    png, svg = save_figure(
        fig, "viz_growth_10y_dotplot",
        headline="Every comparator market has kept growing — CLOs have no free, current figure to plot alongside them.",
        subtitle="10-year compound annual growth rate of amount outstanding, by market.",
        source="clo-atlas, from FRED (Treasury/Fed series)",
        notes="CLO's own growth rate is not shown: the only free CLO-outstanding figure found is a single Dec-2018 snapshot, with no second point to compute a CAGR from.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_market_size_bars()
    viz_growth_10y_dotplot()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
