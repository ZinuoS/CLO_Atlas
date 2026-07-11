"""Distribution-cut resilience exhibit (Section 2 deep-dive): OXLC's
premium immediately before/after each detected distribution cut.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.cef.viz_distribution")

CUTS_PATH = config.FINAL_DIR / "distribution_cuts_vs_premium.parquet"


def viz_distribution_cuts_vs_premium():
    apply_theme()
    df = read_parquet(CUTS_PATH)
    if df.empty:
        logger.warning("no distribution-cut data; skipping viz_distribution_cuts_vs_premium")
        return None
    df = df.dropna(subset=["premium_before", "premium_after"], how="all").copy()
    df["ex_date"] = pd.to_datetime(df["ex_date"])
    df = df.sort_values("ex_date")
    if df.empty:
        logger.warning("no distribution-cut events with any premium context; skipping")
        return None

    fig, ax = plt.subplots(figsize=(8, 5))
    for i, row in df.reset_index(drop=True).iterrows():
        y = i
        if pd.notna(row["premium_before"]):
            ax.scatter([row["premium_before"] * 100], [y], color=WARM_GRAY[1], s=90, zorder=3, label="Before cut" if i == 0 else None)
        if pd.notna(row["premium_after"]):
            ax.scatter([row["premium_after"] * 100], [y], color=ACCENT, s=90, zorder=3, label="After cut" if i == 0 else None)
        if pd.notna(row["premium_before"]) and pd.notna(row["premium_after"]):
            ax.plot([row["premium_before"] * 100, row["premium_after"] * 100], [y, y], color=WARM_GRAY[2], lw=1.5, zorder=1)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels([f"{d.strftime('%b %Y')} ({c*100:.0f}%)" for d, c in zip(df["ex_date"], df["change_pct"])])
    ax.set_xlabel("Premium/(discount) to NAV (%)")
    ax.axvline(0, color=INK, linewidth=0.8)
    ax.legend(loc="lower right", fontsize=8.5, frameon=False)
    fig.subplots_adjust(left=0.3)
    png, svg = save_figure(
        fig, "viz_distribution_cuts_vs_premium",
        headline="OXLC's premium has compressed after cuts, but never fully disappeared.",
        subtitle="Premium/(discount) to disclosed NAV immediately before vs. after each detected distribution cut (% is the cut size).",
        source="clo-atlas, from EDGAR 424B3/497 NAV disclosures + Yahoo Finance dividend history",
        notes="Premium disclosures are sparse (only available from month-ends OXLC's own filings happened to state) — "
              "several older cuts have no premium data point close enough in time to show.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_distribution_cuts_vs_premium()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
