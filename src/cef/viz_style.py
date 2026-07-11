"""Portfolio-style exhibits (Section 2 deep-dive): shelf concentration and
vintage mix from position-level CLO equity holdings. `shelf_name` is a
deal-name-prefix proxy for manager identity, not a verified mapping — see
analysis_portfolio_style.py's docstring.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.cef.viz_style")

SHELF_PATH = config.FINAL_DIR / "portfolio_shelf_concentration.parquet"
VINTAGE_PATH = config.FINAL_DIR / "portfolio_vintage_mix.parquet"


def viz_shelf_concentration(fund: str = "ECC", top_n: int = 10):
    apply_theme()
    df = read_parquet(SHELF_PATH)
    if df.empty:
        logger.warning("no shelf-concentration data; skipping viz_shelf_concentration")
        return None
    sub = df[df["fund"] == fund].nlargest(top_n, "total_valUSD").sort_values("total_valUSD")
    if sub.empty:
        logger.warning("no shelf data for fund %s; skipping viz_shelf_concentration", fund)
        return None

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.barh(sub["shelf_name"], sub["share_of_fund"] * 100, color=ACCENT)
    for i, (_, row) in enumerate(sub.iterrows()):
        ax.annotate(f"{row['share_of_fund']*100:.1f}% ({row['n_positions']} positions)",
                    xy=(row["share_of_fund"] * 100, i), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8.5, color=INK)
    ax.set_xlabel("Share of fund's CLO equity holdings (%)")
    ax.set_xlim(0, sub["share_of_fund"].max() * 100 * 1.35)
    fig.subplots_adjust(left=0.32)
    png, svg = save_figure(
        fig, "viz_shelf_concentration",
        headline=f"{fund}'s CLO equity book concentrates in a handful of repeat manager shelves.",
        subtitle=f"Top {top_n} deal shelves by fair value, most recent NPORT-P filing. \"Shelf name\" is a deal-name-prefix "
                 "proxy for manager identity, not a verified manager mapping.",
        source="clo-atlas, from EDGAR NPORT-P filings",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_vintage_mix():
    apply_theme()
    df = read_parquet(VINTAGE_PATH)
    if df.empty:
        logger.warning("no vintage-mix data; skipping viz_vintage_mix")
        return None

    funds = sorted(df["fund"].unique())
    bands = sorted(df["maturity_band"].unique())
    fig, ax = plt.subplots(figsize=(8.5, 5))
    bottom = {f: 0.0 for f in funds}
    for i, band in enumerate(bands):
        heights = [df[(df["fund"] == f) & (df["maturity_band"] == band)]["share_of_fund"].sum() * 100 for f in funds]
        color = ACCENT if i == len(bands) - 1 else WARM_GRAY[i % len(WARM_GRAY)]
        ax.bar(funds, heights, bottom=[bottom[f] for f in funds], color=color, label=band, width=0.6)
        for j, f in enumerate(funds):
            bottom[f] += heights[j]

    ax.set_ylabel("Share of CLO equity holdings by tranche maturity band (%)")
    ax.legend(title="Maturity band (vintage proxy)", loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=8, frameon=False)
    fig.subplots_adjust(right=0.78)
    png, svg = save_figure(
        fig, "viz_vintage_mix",
        headline="Vintage mix by tranche maturity band, across the listed CLO CEF universe.",
        subtitle="Share of each fund's CLO equity holdings by tranche maturity band — a vintage proxy, since NPORT-P "
                 "doesn't carry each deal's original closing date.",
        source="clo-atlas, from EDGAR NPORT-P filings",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_shelf_concentration()
    viz_vintage_mix()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
