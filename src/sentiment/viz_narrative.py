"""CDO-comparison narrative frequency over time (Section 6)."""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, apply_theme, format_date_axis, save_figure

logger = logging.getLogger("clo_atlas.sentiment.viz_narrative")

FREQ_PATH = config.FINAL_DIR / "cdo_comparison_frequency.parquet"


def viz_cdo_comparison_frequency():
    apply_theme()
    df = read_parquet(FREQ_PATH)
    if df.empty:
        logger.warning("no CDO-comparison frequency data cached; skipping viz_cdo_comparison_frequency")
        return None
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    by_date = df.groupby("date")["mentions_per_1000"].sum().reset_index().sort_values("date")

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(by_date["date"], by_date["mentions_per_1000"], color=ACCENT, marker="o", markersize=4)
    format_date_axis(ax, interval_months=12)
    ax.set_ylabel("CDO/2008-comparison mentions per 1,000 tokens")

    png, svg = save_figure(
        fig, "viz_cdo_comparison_frequency",
        headline="'CLOs are the new CDOs' language shows up unevenly across regulator reports.",
        subtitle="Combined rate of CDO/2008/subprime-comparison language in Fed FSR, BIS Quarterly Review, and ECB FSR text.",
        source="clo-atlas, from Federal Reserve FSR, BIS Quarterly Review, and ECB FSR PDFs",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_cdo_comparison_frequency()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
