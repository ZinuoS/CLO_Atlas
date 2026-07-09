"""CLO manager league exhibits (Section 1).

The bump chart (rankings over time) needs >=2 scrape_holdings.py dates;
today this ships the current top-10 manager league table and the fund-
overlap read, both real reads from the latest scrape date.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import apply_theme, categorical_color, save_figure

logger = logging.getLogger("clo_atlas.etf.viz_league")

LEAGUE_PATH = config.FINAL_DIR / "etf_manager_league.parquet"
OVERLAP_PATH = config.FINAL_DIR / "etf_fund_overlap_jaccard.parquet"


def viz_top10_managers():
    apply_theme()
    league = read_parquet(LEAGUE_PATH)
    if league.empty:
        logger.warning("no manager league data cached; skipping viz_top10_managers")
        return None

    latest_date = league["date"].max()
    top10 = league[league["date"] == latest_date].nlargest(10, "total_par").sort_values("total_par")

    fig, ax = plt.subplots(figsize=(9, 5.5))
    colors = [categorical_color(0) if i == len(top10) - 1 else categorical_color(1) for i in range(len(top10))]
    ax.barh(top10["canonical_manager"], top10["total_par"] / 1e9, color=colors)
    ax.set_xlabel("Par held across tracked CLO ETFs ($ billions)")
    fig.subplots_adjust(left=0.34)

    png, svg = save_figure(
        fig, "viz_top10_managers",
        headline="A handful of CLO managers supply most of what the ETF complex buys.",
        subtitle=f"Top 10 CLO managers by par value held across tracked ETFs, as of {latest_date}. "
                  "A ranking-over-time bump chart accretes as more scrape dates accumulate.",
        source="clo-atlas, Janus Henderson holdings, entity-resolved",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_top10_managers()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
