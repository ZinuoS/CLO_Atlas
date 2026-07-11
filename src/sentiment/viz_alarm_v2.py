"""Rebuilt regulatory alarm index exhibits (Section 6 v2).

(a) Per-institution small multiples of the additive alarm index, with a
    coverage strip (one tick per scored document) along the bottom of each
    panel so sparsity is visible rather than implied.
(b) The three components (mention rate, vulnerability rate, LM negative
    rate) plotted separately, pooled across institutions — so a coverage
    spike without negative tone doesn't vanish into a summed index.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK_MUTED, WARM_GRAY, apply_theme, format_date_axis, save_figure

logger = logging.getLogger("clo_atlas.sentiment.viz_alarm_v2")

REPORT_LEVEL_PATH = config.FINAL_DIR / "alarm_v2_by_report.parquet"
COVERAGE_PATH = config.FINAL_DIR / "alarm_v2_coverage.parquet"


def viz_alarm_index_small_multiples():
    apply_theme()
    df = read_parquet(REPORT_LEVEL_PATH)
    if df.empty:
        logger.warning("no alarm v2 data; skipping viz_alarm_index_small_multiples")
        return None
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    institutions = sorted(df["institution"].unique())

    fig, axes = plt.subplots(len(institutions), 1, figsize=(9.5, 2.6 * len(institutions)), sharex=True)
    axes = axes if len(institutions) > 1 else [axes]
    date_min, date_max = df["date"].min(), df["date"].max()
    for ax, inst in zip(axes, institutions):
        sub = df[df["institution"] == inst].sort_values("date")
        ax.axhline(0, color=INK_MUTED, linewidth=0.8)
        ax.plot(sub["date"], sub["alarm_index_v2"], color=ACCENT, marker="o", markersize=4, linewidth=1.6)
        # Coverage strip: a tick per scored document, at the bottom of each panel.
        ymin, ymax = ax.get_ylim()
        tick_y = ymin - (ymax - ymin) * 0.06
        ax.scatter(sub["date"], [tick_y] * len(sub), marker="|", color=WARM_GRAY[1], s=40, clip_on=False)
        ax.set_ylim(ymin - (ymax - ymin) * 0.12, ymax)
        ax.set_xlim(date_min, date_max)
        ax.set_title(f"{inst}  (n={len(sub)})", loc="left", fontsize=10)

    format_date_axis(axes[-1], interval_months=12)
    png, svg = save_figure(
        fig, "viz_alarm_index_small_multiples",
        headline="Regulatory alarm about CLOs is real, institution-specific, and mostly episodic.",
        subtitle="Additive alarm index (institution-z-scored mentions + vulnerability-lexicon rate + LM negative rate) per report. "
                 "Tick marks below each line mark every document actually scored — sparsity is real, not hidden.",
        source="clo-atlas, from Fed FSR / BIS Quarterly Review / ECB FSR text, domain-scored",
        notes="Replaces the original VADER-based multiplicative index, which scored ~37 of 40 reports at exactly zero.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_alarm_components():
    apply_theme()
    df = read_parquet(REPORT_LEVEL_PATH)
    if df.empty:
        logger.warning("no alarm v2 data; skipping viz_alarm_components")
        return None
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    components = [("z_mentions_per_1000", "Coverage (mention rate)"),
                  ("z_vulnerability_rate", "Vulnerability lexicon"),
                  ("z_lm_negative_rate", "LM negative rate")]
    fig, axes = plt.subplots(len(components), 1, figsize=(9.5, 2.4 * len(components)), sharex=True)
    for ax, (col, label) in zip(axes, components):
        for i, inst in enumerate(sorted(df["institution"].unique())):
            sub = df[df["institution"] == inst]
            color = ACCENT if i == 0 else WARM_GRAY[min(i, len(WARM_GRAY) - 1)]
            ax.plot(sub["date"], sub[col], color=color, marker="o", markersize=3, linewidth=1.2, label=inst)
        ax.axhline(0, color=INK_MUTED, linewidth=0.8)
        ax.set_title(label, loc="left", fontsize=10)
    axes[0].legend(loc="upper left", fontsize=8, frameon=False, ncol=3)
    format_date_axis(axes[-1], interval_months=12)
    png, svg = save_figure(
        fig, "viz_alarm_components",
        headline="Coverage, vulnerability language, and negative tone don't always move together.",
        subtitle="The three inputs to the additive alarm index, institution-z-scored and plotted separately, so a coverage "
                 "spike without negative tone stays visible instead of being summed away.",
        source="clo-atlas, from Fed FSR / BIS Quarterly Review / ECB FSR text",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_alarm_index_small_multiples()
    viz_alarm_components()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
