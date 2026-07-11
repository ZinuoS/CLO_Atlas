"""Cost-of-capital exhibit (Section 2 deep-dive): portfolio effective yield
vs. blended preferred/baby-bond cost of capital, margin shaded.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.cef.viz_cost_of_capital")

MARGIN_PATH = config.FINAL_DIR / "cost_of_capital_margin.parquet"


def viz_cost_of_capital_margin():
    apply_theme()
    df = read_parquet(MARGIN_PATH)
    if df.empty:
        logger.warning("no cost-of-capital margin data; skipping viz_cost_of_capital_margin")
        return None

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = range(len(df))
    ax.bar(x, df["portfolio_effective_yield"], color=WARM_GRAY[2], width=0.5, label="Portfolio effective yield")
    ax.bar(x, df["blended_cost_of_capital"] * 100, color=ACCENT, width=0.25, label="Blended preferred cost of capital")
    for i, (_, row) in enumerate(df.iterrows()):
        ax.annotate(f"+{row['margin']*100:.1f}pp margin", xy=(i, row["portfolio_effective_yield"]), xytext=(0, 6),
                    textcoords="offset points", ha="center", fontsize=9, color=INK, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["fund"])
    ax.set_ylabel("Annualized yield (%)")
    ax.legend(loc="upper right", fontsize=8.5, frameon=False)
    png, svg = save_figure(
        fig, "viz_cost_of_capital_margin",
        headline="Both funds run a real, positive margin between what they earn and what their preferred capital costs.",
        subtitle="Par-weighted portfolio effective yield (CLO equity positions, NPORT-P) vs. blended current yield on "
                 "listed preferred/baby-bond capital, most recent data.",
        source="clo-atlas, from EDGAR NPORT-P + Yahoo Finance preferred prices",
        notes="Preferred current yield = $25 par x coupon / price, not yield-to-call; coupon per ticker approximated "
              "as the fund's median outstanding series coupon.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_cost_of_capital_margin()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
