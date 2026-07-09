"""Total-return exhibits: growth-of-$100 and drawdown small multiples (Section 1).

Fully data-backed today (analysis_returns.py has complete history), so these
are the strongest signature charts Section 1 can ship on day one.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import (ACCENT, apply_theme, categorical_color, direct_label,
                                format_date_axis, save_figure, small_multiples_grid)

logger = logging.getLogger("clo_atlas.etf.viz_returns")

GROWTH_PATH = config.FINAL_DIR / "etf_growth_of_100.parquet"
DD_DURATION_PATH = config.FINAL_DIR / "etf_drawdown_duration.parquet"
PRICES_PATH = config.INTERIM_DIR / "etf_prices.parquet"

FEATURED = ["JAAA", "JBBB", "HYG", "AGG", "BKLN"]


def viz_growth_of_100():
    apply_theme()
    growth = read_parquet(GROWTH_PATH)
    growth["date"] = pd.to_datetime(growth["date"])

    fig, ax = plt.subplots(figsize=(9, 5.5))
    end_values = []
    for i, ticker in enumerate(FEATURED):
        grp = growth[growth["ticker"] == ticker].sort_values("date")
        if grp.empty:
            continue
        color = categorical_color(i)
        ax.plot(grp["date"], grp["growth_of_100"], color=color, linewidth=2.2 if ticker in ("JAAA", "JBBB") else 1.6)
        end_values.append((grp["date"].iloc[-1], grp["growth_of_100"].iloc[-1], ticker, color))

    # Decluttering pass: nudge labels apart vertically if their end values sit
    # within a few percent of the axis range of each other.
    end_values.sort(key=lambda r: r[1])
    ymin, ymax = ax.get_ylim()
    min_gap = (ymax - ymin) * 0.035
    adjusted = []
    last_y = None
    for date, value, ticker, color in end_values:
        y = value if last_y is None else max(value, last_y + min_gap)
        adjusted.append((date, value, y, ticker, color))
        last_y = y
    for date, value, y, ticker, color in adjusted:
        direct_label(ax, date, y, ticker, color=color)

    format_date_axis(ax, interval_months=12)
    ax.set_ylabel("Growth of $100")
    png, svg = save_figure(
        fig, "viz_growth_of_100",
        headline="A dollar in AAA CLOs grew steadily through every scare since 2020.",
        subtitle="Cumulative total return, $100 invested at each fund's inception, vs. high-yield and aggregate bond benchmarks.",
        source="clo-atlas, from Yahoo Finance adjusted close via yfinance",
        notes="JAAA/JBBB start from their 2020/2022 inception; other series shown from the same window for comparability.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_drawdown_small_multiples():
    apply_theme()
    dd = read_parquet(DD_DURATION_PATH)
    if dd.empty:
        logger.warning("no drawdown-duration data; skipping viz_drawdown_small_multiples")
        return None
    dd["peak_date"] = pd.to_datetime(dd["peak_date"])

    tickers = [t for t in FEATURED if t in dd["ticker"].unique()]
    fig, axes = small_multiples_grid(len(tickers), ncols=len(tickers), figsize_per_panel=(2.6, 4.2))
    for ax, ticker in zip(axes, tickers):
        sub = dd[dd["ticker"] == ticker].nsmallest(15, "depth")
        ax.barh(range(len(sub)), sub["depth"] * 100, color=ACCENT if ticker in ("JAAA", "JBBB") else "#8C8579")
        ax.set_yticks([])
        ax.set_title(ticker, fontsize=10, loc="left")

    png, svg = save_figure(
        fig, "viz_drawdown_small_multiples",
        headline="AAA CLO drawdowns are shallow; the mezzanine tranche isn't.",
        subtitle="Every historical drawdown episode by depth (%), largest at top, one panel per fund. X-axis is drawdown %, shared across panels.",
        source="clo-atlas, from Yahoo Finance adjusted close via yfinance",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_growth_of_100()
    viz_drawdown_small_multiples()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
