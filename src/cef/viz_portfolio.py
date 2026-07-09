"""Disclosed CLO-equity portfolio economics, from NPORT-P (Section 2).

The four most recent quarterly filings per fund give a real (if short)
weighted-yield time series today — the CCC%/OC-cushion trajectories from the
mission brief aren't in NPORT-P (position-level credit stats aren't
disclosed there); see analysis_portfolio.py's docstring.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import apply_theme, categorical_color, direct_label, save_figure

logger = logging.getLogger("clo_atlas.cef.viz_portfolio")

YIELD_PATH = config.FINAL_DIR / "cef_weighted_effective_yield.parquet"


def viz_weighted_yield_trend():
    apply_theme()
    df = read_parquet(YIELD_PATH)
    if df.empty:
        logger.warning("no weighted-yield data cached; skipping viz_weighted_yield_trend")
        return None
    df = df.dropna(subset=["weighted_yield"]).copy()
    df["period"] = pd.to_datetime(df["period"])

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for i, (fund, grp) in enumerate(df.groupby("fund")):
        grp = grp.sort_values("period")
        if len(grp) < 2:
            continue
        color = categorical_color(i)
        ax.plot(grp["period"], grp["weighted_yield"], color=color, marker="o", markersize=5)
        direct_label(ax, grp["period"].iloc[-1], grp["weighted_yield"].iloc[-1], fund, color=color)
    ax.set_ylabel("Par-weighted effective yield on disclosed CLO positions")

    png, svg = save_figure(
        fig, "viz_weighted_yield_trend",
        headline="Disclosed CLO-equity yields swung by fund, not in lockstep.",
        subtitle="Par-weighted average effective yield on each fund's CLO-tagged NPORT-P positions, "
                  "most recent 4 filings per fund (reporting cadence varies by fund).",
        source="clo-atlas, from SEC EDGAR NPORT-P filings",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_weighted_yield_trend()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
