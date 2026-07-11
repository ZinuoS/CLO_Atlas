"""The leverage-gradient exhibit (Section 2 deep-dive): JAAA -> BKLN ->
OXLC/ECC, teaching the whole CLO capital structure through instruments a
desk can quote.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.cef.viz_wrapper")

BETA_PATH = config.FINAL_DIR / "nav_translation_beta.parquet"
DRAWDOWN_PATH = config.FINAL_DIR / "nav_translation_drawdown_ladder.parquet"

ORDER = ["JAAA", "BKLN", "ECC", "OXLC"]
LABELS = {"JAAA": "JAAA\n(AAA CLO ETF)", "BKLN": "BKLN\n(unlevered loans)",
          "ECC": "ECC\n(levered CLO equity)", "OXLC": "OXLC\n(levered CLO equity)"}


def viz_leverage_gradient():
    apply_theme()
    beta = read_parquet(BETA_PATH)
    drawdown = read_parquet(DRAWDOWN_PATH)
    if beta.empty or drawdown.empty:
        logger.warning("no NAV-translation data; skipping viz_leverage_gradient")
        return None
    merged = beta.merge(drawdown, on="ticker")
    merged["ticker"] = pd.Categorical(merged["ticker"], categories=ORDER, ordered=True)
    merged = merged.sort_values("ticker")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.8))
    colors = [ACCENT if t in ("OXLC", "ECC") else WARM_GRAY[1] for t in merged["ticker"]]

    ax1.bar(merged["ticker"].astype(str), merged["beta_to_bkln"], color=colors)
    ax1.set_ylabel("Price beta to BKLN (loans)")
    ax1.set_xticklabels([LABELS[t] for t in merged["ticker"]], fontsize=8.5)
    ax1.axhline(1, color=INK, linewidth=0.8, linestyle=":")

    ax2.bar(merged["ticker"].astype(str), merged["max_drawdown"] * 100, color=colors)
    ax2.set_ylabel("Max drawdown since 2020 (%)")
    ax2.set_xticklabels([LABELS[t] for t in merged["ticker"]], fontsize=8.5)

    png, svg = save_figure(
        fig, "viz_leverage_gradient",
        headline="Same underlying loans, three leverage levels — one AAA-insulated, one unlevered, two double-levered.",
        subtitle="Price beta to BKLN (broadly syndicated loans) and max drawdown since 2020, across the CLO capital structure "
                 "from AAA tranche to levered CLO-equity closed-end funds.",
        source="clo-atlas, from Yahoo Finance adjusted close via yfinance",
        notes="OXLC/ECC use market price as a NAV-translation proxy — true historical NAV isn't available for these tickers.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_leverage_gradient()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
