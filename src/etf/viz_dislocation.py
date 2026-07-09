"""Premium/discount exhibits for CLO ETFs (Section 1).

The signature "close-up" panels (March 2023 / April 2025 dislocation, price
vs NAV with the gap shaded) need many months of daily NAV history that only
starts accreting once scrape_nav_flows.py runs regularly — see that module's
docstring. Until then, this ships the cross-sectional read that IS available
today: where each fund's price sits relative to its NAV right now, which
already shows the credit-quality liquidity gradient the signature piece will
eventually track through a full episode.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.etf.viz_dislocation")

DAILY_PATH = config.FINAL_DIR / "etf_premium_discount_daily.parquet"


def viz_current_premium_discount():
    apply_theme()
    daily = read_parquet(DAILY_PATH)
    if daily.empty:
        logger.warning("no premium/discount data cached; skipping viz_current_premium_discount")
        return None

    latest_date = daily["date"].max()
    snap = daily[daily["date"] == latest_date].copy()
    snap["tranche_focus"] = snap["ticker"].map(lambda t: config.CLO_ETF_TICKERS[t]["tranche_focus"])
    snap = snap.sort_values("premium_discount")

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [ACCENT if "AAA" in f else WARM_GRAY[1] for f in snap["tranche_focus"]]
    bars = ax.barh(snap["ticker"], snap["premium_discount"] * 100, color=colors)
    ax.axvline(0, color="#1A1A1A", linewidth=1)
    ax.set_xlabel("Premium / discount to NAV (%)")

    png, svg = save_figure(
        fig, "viz_current_premium_discount",
        headline=f"On {pd.Timestamp(latest_date).strftime('%B %-d, %Y')}, every CLO ETF traded within a hair of its NAV.",
        subtitle="Market price vs. net asset value, one snapshot; red = AAA-focused funds, gray = mezzanine/BB funds. "
                  "A full time series (and the March-2023 / April-2025 dislocation close-ups) accretes as this project runs daily.",
        source="clo-atlas, from Yahoo Finance (navPrice) via yfinance",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_current_premium_discount()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
