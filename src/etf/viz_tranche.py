"""AAA tranche mark exhibits (Section 1).

The ribbon-over-time and pre/post-episode slope chart both need >=2
scrape_holdings.py dates; today this ships the cross-sectional distribution
of every AAA CUSIP's mark on the latest scrape date, which is itself a real
"stress thermometer" reading (a tight distribution = an orderly market).
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, apply_theme, save_figure
from src.etf.analysis_tranche_panel import load_holdings

logger = logging.getLogger("clo_atlas.etf.viz_tranche")

DISPERSION_PATH = config.FINAL_DIR / "etf_aaa_mark_dispersion.parquet"


def viz_aaa_mark_distribution():
    apply_theme()
    holdings = load_holdings()
    aaa_funds = [t for t, m in config.CLO_ETF_TICKERS.items() if m["tranche_focus"] == "AAA"]
    aaa = holdings[holdings["fund"].isin(aaa_funds)]
    if aaa.empty:
        logger.warning("no AAA holdings cached; skipping viz_aaa_mark_distribution")
        return None

    latest_date = aaa["date"].max()
    snap = aaa[aaa["date"] == latest_date]
    disp = read_parquet(DISPERSION_PATH)
    disp_row = disp[disp["date"] == latest_date].iloc[0] if len(disp) else None

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(snap["price"], bins=40, color=ACCENT, alpha=0.85)
    if disp_row is not None:
        ax.axvline(disp_row["median_price"], color="#1A1A1A", linewidth=1.2, linestyle="--")
        ax.annotate(f"median {disp_row['median_price']:.2f}", xy=(disp_row["median_price"], ax.get_ylim()[1] * 0.95),
                    fontsize=8, color="#1A1A1A", ha="left")
    ax.set_xlabel("Mark (par = 100)")
    ax.set_ylabel("Number of AAA positions")

    iqr_txt = f"IQR {disp_row['iqr']:.2f} pts" if disp_row is not None else ""
    png, svg = save_figure(
        fig, "viz_aaa_mark_distribution",
        headline=f"On {pd.Timestamp(latest_date).strftime('%B %-d, %Y')}, AAA CLO marks clustered tightly around par.",
        subtitle=f"Distribution of {len(snap)} AAA tranche marks held across {snap['fund'].nunique()} fund(s). {iqr_txt} "
                  "— the dispersion series over time (a stress thermometer) accretes as more scrape dates accumulate.",
        source="clo-atlas, from Janus Henderson full-holdings pages",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_aaa_mark_distribution()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
