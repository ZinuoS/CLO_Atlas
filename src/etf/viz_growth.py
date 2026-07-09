"""CLO ETF complex growth exhibits (Section 1).

The stacked-area AUM-over-time chart and the monthly-flow bars need,
respectively, multiple AUM snapshot dates and >=2 NAV snapshot dates — see
analysis_flows.py's docstring for why that accretes going forward rather
than back-filling. Today this ships the launch timeline (real, back-filled
from full price history) and current AUM by fund (real, single date).
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import apply_theme, categorical_color, format_date_axis, save_figure

logger = logging.getLogger("clo_atlas.etf.viz_growth")

LAUNCH_PATH = config.FINAL_DIR / "etf_launch_timeline.parquet"
AUM_PATH = config.FINAL_DIR / "etf_aum_by_scrape_date.parquet"
FLOWS_PATH = config.FINAL_DIR / "etf_flows_monthly.parquet"


def viz_launch_timeline():
    apply_theme()
    launch = read_parquet(LAUNCH_PATH)
    if launch.empty:
        logger.warning("no launch timeline cached; skipping viz_launch_timeline")
        return None
    launch = launch.sort_values("launch_date").reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, row in launch.iterrows():
        ax.scatter(row["launch_date"], i, color=categorical_color(0 if row["ticker"] in ("JAAA", "JBBB") else 1), s=50, zorder=3)
        ax.annotate(f"{row['ticker']}  ({row['issuer']})", xy=(row["launch_date"], i), xytext=(8, 0),
                     textcoords="offset points", va="center", fontsize=9.5)
    ax.set_yticks([])
    ax.set_ylim(-1, len(launch) + 1)
    format_date_axis(ax, interval_months=6)

    png, svg = save_figure(
        fig, "viz_launch_timeline",
        headline="The CLO ETF complex is a five-year-old market that's only getting more crowded.",
        subtitle="First trading day for each tracked CLO ETF, oldest at bottom.",
        source="clo-atlas, from Yahoo Finance price history via yfinance",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_current_aum():
    apply_theme()
    aum = read_parquet(AUM_PATH)
    if aum.empty:
        logger.warning("no AUM snapshot cached; skipping viz_current_aum")
        return None
    latest_date = aum["date"].max()
    snap = aum[aum["date"] == latest_date].sort_values("aum")
    if snap.empty:
        return None

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(snap["fund"], snap["aum"] / 1e9,
            color=[categorical_color(0 if t in ("JAAA", "JBBB") else 1) for t in snap["fund"]])
    ax.set_xlabel("AUM ($ billions)")
    fig.subplots_adjust(left=0.16)

    png, svg = save_figure(
        fig, "viz_current_aum",
        headline="Janus Henderson's AAA fund dwarfs the rest of the CLO ETF complex.",
        subtitle=f"Assets under management by fund, as of {latest_date}. A full AUM-over-time stacked area accretes as this project runs daily.",
        source="clo-atlas, from issuer total-assets snapshots via yfinance",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_monthly_flows():
    flows = read_parquet(FLOWS_PATH)
    if flows.empty:
        logger.warning("flows_monthly is empty (need >=2 NAV snapshot dates); skipping viz_monthly_flows for now")
        return None
    apply_theme()
    fig, ax = plt.subplots(figsize=(9, 5))
    pivot = flows.pivot(index="month", columns="ticker", values="estimated_flow_usd").fillna(0)
    pivot.plot(kind="bar", stacked=True, ax=ax, color=[categorical_color(i) for i in range(len(pivot.columns))])
    ax.set_ylabel("Estimated monthly flow ($)")
    png, svg = save_figure(
        fig, "viz_monthly_flows",
        headline="Money moved into CLO ETFs in bursts, not a steady drip.",
        subtitle="Estimated creation/redemption-driven flow by fund and month.",
        source="clo-atlas, from issuer total-assets snapshots via yfinance",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_launch_timeline()
    viz_current_aum()
    viz_monthly_flows()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
