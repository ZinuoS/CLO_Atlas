"""Spread distribution over time from BDC SOI (Section 3)."""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, ACCENT_SOFT, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.edgar.viz_terms")

SPREAD_PATH = config.FINAL_DIR / "edgar_spread_distribution.parquet"


def viz_spread_distribution():
    apply_theme()
    df = read_parquet(SPREAD_PATH)
    if df.empty:
        logger.warning("no spread distribution data cached; skipping viz_spread_distribution")
        return None
    df = df.sort_values("period")
    x = range(len(df))

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.fill_between(x, df["p25"], df["p75"], color=ACCENT_SOFT, alpha=0.6, label="25th-75th percentile")
    ax.plot(x, df["median_spread"], color=ACCENT, marker="o", linewidth=2, label="Median")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["period"], rotation=0)
    ax.set_ylabel("Spread (percentage points over reference rate)")

    first_med, last_med = df["median_spread"].iloc[0], df["median_spread"].iloc[-1]
    direction = "compressed" if last_med < first_med else "widened"
    headline = f"Median loan spreads {direction} about {abs(first_med - last_med):.1f} points from {df['period'].iloc[0]} to {df['period'].iloc[-1]}."
    png, svg = save_figure(
        fig, "viz_spread_distribution",
        headline=headline,
        subtitle=f"Distribution of disclosed spreads on BDC SOI positions, by reporting period (n={int(df['n'].sum())} positions).",
        source="clo-atlas, from SEC EDGAR BDC Schedules of Investment",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_spread_distribution()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
