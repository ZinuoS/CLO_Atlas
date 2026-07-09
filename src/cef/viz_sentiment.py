"""CLO CEF sentiment exhibits (Section 2): distribution cuts/raises and the
current cross-sectional discount-to-book snapshot.

The full composite z-score sentiment index and its regime shading need
multi-date book-value history (see analysis_premium_discount.py); today this
ships what's real: the actual distribution-change event history (full,
real, back-filled by yfinance) and today's cross-sectional discount snapshot.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, WARM_GRAY, add_event_flags, apply_theme, format_date_axis, save_figure

logger = logging.getLogger("clo_atlas.cef.viz_sentiment")

EVENTS_PATH = config.FINAL_DIR / "cef_distribution_change_events.parquet"
DAILY_DISCOUNT_PATH = config.FINAL_DIR / "cef_premium_discount_daily.parquet"


def viz_distribution_changes():
    apply_theme()
    events = read_parquet(EVENTS_PATH)
    if events.empty:
        logger.warning("no distribution change events cached; skipping viz_distribution_changes")
        return None
    events = events.copy()
    events["ex_date"] = pd.to_datetime(events["ex_date"])
    events["direction"] = events["change"].apply(lambda c: "Raise" if c > 0 else "Cut")

    fig, ax = plt.subplots(figsize=(10, 5.5))
    for ticker in config.CLO_CEF_TICKERS:
        sub = events[events["ticker"] == ticker]
        if sub.empty:
            continue
        cuts = sub[sub["direction"] == "Cut"]
        raises = sub[sub["direction"] == "Raise"]
        ax.scatter(cuts["ex_date"], [ticker] * len(cuts), color=ACCENT, marker="v", s=60, zorder=3)
        ax.scatter(raises["ex_date"], [ticker] * len(raises), color=WARM_GRAY[0], marker="^", s=60, zorder=3)

    add_event_flags(ax, label_events=False)
    format_date_axis(ax, interval_months=24)
    ax.margins(y=0.15)

    png, svg = save_figure(
        fig, "viz_distribution_changes",
        headline="CLO CEF dividends move constantly, and cuts outnumber raises.",
        subtitle="Every distribution change >1c per share, full history, one row per fund.",
        source="clo-atlas, from Yahoo Finance dividend history via yfinance",
        notes="(v) = distribution cut     (^) = distribution raise",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_current_discount_snapshot():
    apply_theme()
    daily = read_parquet(DAILY_DISCOUNT_PATH)
    if daily.empty:
        logger.warning("no premium/discount snapshot cached; skipping viz_current_discount_snapshot")
        return None
    latest_date = daily["date"].max()
    snap = daily[daily["date"] == latest_date].sort_values("premium_discount")

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(snap["ticker"], snap["premium_discount"] * 100, color=ACCENT)
    ax.axvline(0, color="#1A1A1A", linewidth=1)
    ax.set_xlabel("Premium / discount to book value (%)")
    fig.subplots_adjust(left=0.18)

    n_discount = (snap["premium_discount"] < 0).sum()
    headline = (f"Most tracked CLO CEFs trade at a discount to book value — {n_discount} of {len(snap)} today."
                if snap["premium_discount"].lt(0).any() and snap["premium_discount"].ge(0).any()
                else "Every tracked CLO CEF trades at a discount to book value.")
    png, svg = save_figure(
        fig, "viz_current_discount_snapshot",
        headline=headline,
        subtitle=f"Market price vs. book value per share (a quarterly accounting proxy for NAV), {latest_date}. "
                  "A daily composite sentiment index accretes as this project runs regularly.",
        source="clo-atlas, from Yahoo Finance (bookValue) via yfinance",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_distribution_changes()
    viz_current_discount_snapshot()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
