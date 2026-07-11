"""The flagship attention/tone exhibit (Section 6 v2): daily headline volume
(attention) as a filled area, vulnerability-lexicon tone as an overlaid
line, event-flagged. Falls back to the headline-count proxy when GDELT is
unavailable (see analysis_attention_tone.py) — the chart says so plainly
rather than silently substituting one series for another.
"""
from __future__ import annotations

import logging

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, WARM_GRAY, add_event_flags, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.sentiment.viz_attention")

GDELT_DAILY_PATH = config.FINAL_DIR / "attention_gdelt_daily.parquet"
HEADLINE_DAILY_PATH = config.FINAL_DIR / "attention_headline_daily.parquet"


def viz_attention_backbone():
    apply_theme()
    gdelt = read_parquet(GDELT_DAILY_PATH) if GDELT_DAILY_PATH.exists() else pd.DataFrame()
    headline = read_parquet(HEADLINE_DAILY_PATH) if HEADLINE_DAILY_PATH.exists() else pd.DataFrame()

    using_gdelt = len(gdelt) > 0
    if not using_gdelt and headline.empty:
        logger.warning("no attention data (GDELT empty and no headline corpus); skipping viz_attention_backbone")
        return None

    fig, ax1 = plt.subplots(figsize=(9.5, 5.5))
    ax2 = ax1.twinx()

    if using_gdelt:
        agg = gdelt.groupby("date").agg(volume=("volume", "sum"), tone=("tone", "mean")).reset_index()
        agg["date"] = pd.to_datetime(agg["date"])
        ax1.fill_between(agg["date"], agg["volume"], color=WARM_GRAY[2], alpha=0.6, label="GDELT article volume")
        ax2.plot(agg["date"], agg["tone"], color=ACCENT, linewidth=1.6, label="GDELT avg. tone")
        ax2.set_ylabel("GDELT average tone")
        source = "clo-atlas, from the GDELT DOC 2.0 API"
    else:
        headline["date"] = pd.to_datetime(headline["date"])
        # Google News RSS / yfinance news only ever return a rolling window
        # of currently-indexed articles; syndicated reprints carry old
        # original publish dates, so the full history is a handful of stray
        # single-article days scattered back to 2019 with the real density
        # concentrated in the last ~90-180 days. Plotting the sparse tail
        # would bury the actual signal, so the exhibit focuses on the dense
        # recent window and says so explicitly.
        window_days = 180
        cutoff = headline["date"].max() - pd.Timedelta(days=window_days)
        headline = headline[headline["date"] >= cutoff].sort_values("date")
        ax1.fill_between(headline["date"], headline["n_headlines"], color=WARM_GRAY[2], alpha=0.6, label="Daily headline count")
        ax2.plot(headline["date"], headline["mean_vulnerability_rate"], color=ACCENT, linewidth=1.6, label="Vulnerability-lexicon rate")
        ax2.set_ylabel("Mean vulnerability-lexicon rate")
        source = "clo-atlas, from Google News RSS + yfinance ticker news headlines"

    ax1.set_ylabel("Daily attention (article/headline count)")
    plot_xlim = ax1.get_xlim()  # captured before add_event_flags, which axvspans the FULL
                                 # config.EVENTS registry (back to 2020) and silently
                                 # expands autoscale past this chart's actual plotted window.
    add_event_flags(ax1, label_events=False)
    ax1.set_xlim(plot_xlim)
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=14) if not using_gdelt else mdates.MonthLocator(interval=1))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d" if not using_gdelt else "%b %Y"))
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9, frameon=False)

    headline_note = "" if using_gdelt else (
        " GDELT (the intended primary source) was unreachable from this project's environment this run — "
        "see docs/excluded_sources.md — so this uses the headline-count/vulnerability-lexicon proxy instead."
    )
    png, svg = save_figure(
        fig, "viz_attention_backbone",
        headline="Attention and tone move independently — a coverage spike is not the same thing as alarm.",
        subtitle=f"Daily {'article volume and average tone' if using_gdelt else 'headline count and vulnerability-lexicon tone'} "
                 f"for CLO-related queries.{headline_note}",
        source=source,
        notes=f"Window: {headline['date'].min().date()} to {headline['date'].max().date()}, {len(headline)} distinct days with coverage."
              if not using_gdelt and len(headline) else "",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_attention_backbone()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
