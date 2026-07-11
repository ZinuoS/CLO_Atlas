"""MM-share proxy exhibit (Part C) — see analysis_composition_shift.py's
docstring for why this is two funds' own holdings, not a market-wide share.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.future.viz_composition")

MM_TREND_PATH = config.FINAL_DIR / "composition_shift_mm_trend.parquet"


def viz_mm_share_proxy():
    apply_theme()
    df = read_parquet(MM_TREND_PATH)
    if df.empty:
        logger.warning("no MM-share proxy data; skipping viz_mm_share_proxy")
        return None

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for fund, grp in df.groupby("fund"):
        ax.plot(grp["period"], grp["mm_share"] * 100, marker="o", color=ACCENT, label=fund)
    ax.set_ylabel("Middle-market-shelf share of CLO equity holdings (%)")
    ax.legend(loc="upper left", fontsize=9, frameon=False)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    png, svg = save_figure(
        fig, "viz_mm_share_proxy",
        headline="A small, real slice of these funds' books already sits in middle-market/private-credit CLO shelves.",
        subtitle="Share of CLO equity holdings in manager shelves publicly known to run middle-market programs, by NPORT-P filing period.",
        source="clo-atlas, from EDGAR NPORT-P + a hand-curated MM-shelf keyword list",
        notes="This is two funds' own holdings composition, NOT a market-wide new-issue BSL-vs-MM share — "
              "Section 5's presale corpus (the originally planned source) is empty.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_mm_share_proxy()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
