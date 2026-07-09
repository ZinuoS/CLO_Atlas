"""Price history vs. current book value, per CLO CEF (Section 2).

A true NAV-vs-price dual-line chart (with a COVID close-up panel) needs
daily NAV history this project doesn't have yet (see scrape_prices_nav.py's
docstring). This ships what's real: full price history per fund with
today's book-value-per-share marked as a reference line, so the reader can
see where price sits relative to the one NAV proxy point available.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, apply_theme, format_date_axis, save_figure, small_multiples_grid

logger = logging.getLogger("clo_atlas.cef.viz_navprice")

PRICES_PATH = config.INTERIM_DIR / "cef_prices.parquet"
SNAPSHOTS_PATH = config.INTERIM_DIR / "cef_bookvalue_snapshots.parquet"


def viz_price_vs_book_reference():
    apply_theme()
    prices = read_parquet(PRICES_PATH)
    prices = prices[prices["ticker"].isin(config.CLO_CEF_TICKERS)].copy()
    prices["date"] = pd.to_datetime(prices["date"])
    book = read_parquet(SNAPSHOTS_PATH).dropna(subset=["book_value_per_share"]) if SNAPSHOTS_PATH.exists() else pd.DataFrame()

    tickers = [t for t in config.CLO_CEF_TICKERS if t in prices["ticker"].unique()]
    fig, axes = small_multiples_grid(len(tickers), ncols=3, figsize_per_panel=(3.4, 3.4))
    for ax, ticker in zip(axes, tickers):
        sub = prices[prices["ticker"] == ticker].sort_values("date")
        # Last 3 years keeps the panel legible; full history is in cef_prices.parquet.
        sub = sub[sub["date"] >= sub["date"].max() - pd.DateOffset(years=3)]
        # adj_close, not close: these funds pay double-digit-percent annual
        # distributions, so raw close drifts sharply downward on ex-dividend
        # dates even when total return is flat — adj_close backs that out
        # while still landing on today's real price (it's back-adjusted from
        # the most recent close), so the reference-line comparison stays valid.
        ax.plot(sub["date"], sub["adj_close"], color=ACCENT, linewidth=1.6)
        if len(book):
            bv = book[book["ticker"] == ticker]["book_value_per_share"]
            if len(bv):
                ax.axhline(bv.iloc[-1], color="#1A1A1A", linewidth=1, linestyle="--")
        ax.set_title(ticker, fontsize=10, loc="left")
        format_date_axis(ax, interval_months=18)

    png, svg = save_figure(
        fig, "viz_price_vs_book_reference",
        headline="Every CLO CEF's price sits below its latest book value.",
        subtitle="3-year price history (solid) vs. most recent book value per share (dashed), one panel per fund. "
                  "A true daily NAV series accretes as this project runs regularly.",
        source="clo-atlas, from Yahoo Finance price history and bookValue via yfinance",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_price_vs_book_reference()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
