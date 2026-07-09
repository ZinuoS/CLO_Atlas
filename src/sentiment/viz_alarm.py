""""The crisis that kept not happening" (Section 6) — signature piece #1:
the regulatory alarm index vs. the CLO senior-tranche impairment record.

The impairment half needs Section 5's rating-action data, which is gated
(S&P Akamai-walled, Fitch has no free API — see docs/excluded_sources.md).
This ships the alarm-index half on its own, honestly labeled, rather than
plotting a flat zero line with no real data behind it.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, WARM_GRAY, add_event_flags, apply_theme, format_date_axis, save_figure

logger = logging.getLogger("clo_atlas.sentiment.viz_alarm")

INDEX_PATH = config.FINAL_DIR / "alarm_index_by_report.parquet"


def viz_alarm_index_over_time():
    apply_theme()
    df = read_parquet(INDEX_PATH)
    if df.empty:
        logger.warning("no alarm index data cached; skipping viz_alarm_index_over_time")
        return None
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    for inst, color in [("Federal Reserve", ACCENT), ("BIS", WARM_GRAY[1])]:
        sub = df[df["institution"] == inst]
        if sub.empty:
            continue
        ax.plot(sub["date"], sub["alarm_index"], color=color, marker="o", markersize=4, label=inst)
    add_event_flags(ax, label_events=False)
    format_date_axis(ax, interval_months=12)
    ax.set_ylabel("Alarm index (mention rate x negativity)")
    ax.legend(loc="upper left", frameon=False)

    n_alarmed = (df["alarm_index"] > 0).sum()
    headline = (f"Regulators sounded alarmed about CLOs in {n_alarmed} of {len(df)} reports checked so far — "
                "mostly around known stress episodes.")
    png, svg = save_figure(
        fig, "viz_alarm_index_over_time",
        headline=headline,
        subtitle="Mention rate x VADER negativity of CLO-mentioning text, Fed Financial Stability Reports "
                  "and BIS Quarterly Reviews, 2020-2026 (0 = net-neutral-or-positive tone that report). The "
                  "companion 'realized impairments stayed near zero' panel needs Section 5's rating-action "
                  "data, which is currently gated (see docs/excluded_sources.md).",
        source="clo-atlas, from Federal Reserve FSR and BIS Quarterly Review PDFs, VADER-scored",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_alarm_index_over_time()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
