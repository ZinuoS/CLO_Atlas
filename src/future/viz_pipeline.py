"""Registered product pipeline exhibit (Part C): cumulative registered
CLO-accessible product filings by wrapper type.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.future.viz_pipeline")

BY_YEAR_PATH = config.FINAL_DIR / "pipeline_registrations_by_year.parquet"


def viz_registrations_by_year():
    apply_theme()
    df = read_parquet(BY_YEAR_PATH)
    if df.empty:
        logger.warning("no pipeline data; skipping viz_registrations_by_year")
        return None

    wrappers = sorted(df["wrapper_type"].unique())
    years = sorted(df["year"].unique())
    fig, ax = plt.subplots(figsize=(9, 5))
    bottom = [0.0] * len(years)
    for i, wrapper in enumerate(wrappers):
        color = ACCENT if "closed" in wrapper.lower() else WARM_GRAY[i % len(WARM_GRAY)]
        heights = [df[(df["year"] == y) & (df["wrapper_type"] == wrapper)]["n_filings"].sum() for y in years]
        ax.bar([str(y) for y in years], heights, bottom=bottom, color=color, label=wrapper, width=0.6)
        bottom = [b + h for b, h in zip(bottom, heights)]

    ax.set_ylabel("CLO-mentioning fund-registration filings")
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    png, svg = save_figure(
        fig, "viz_registrations_by_year",
        headline="Registered, CLO-accessible fund products have kept arriving every year measured.",
        subtitle="EDGAR fund-registration filings (N-2, 485APOS, N-1A) mentioning CLOs, by wrapper type and filing year.",
        source="clo-atlas, from EDGAR full-text search (efts.sec.gov)",
        notes="Bounded by EDGAR full-text search's ~30-filings-per-form sample per run, not an exhaustive count.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_registrations_by_year()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
