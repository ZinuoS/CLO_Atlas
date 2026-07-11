"""Slide 1 exhibits: "The regime changed. Most portfolios didn't."

(a) 35-year policy-rate line, regime-shaded, current plateau in accent.
(b) "The duration bill": indexed total return of AGG/TLT/BKLN/SHV/JAAA from
    Dec 2021 to present, direct-labeled at line ends, drawdown troughs
    annotated with their number and recovery status.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import pandas as pd

import config
from src.common.cache import read_parquet
from src.common.style import (ACCENT, INK_MUTED, WARM_GRAY, apply_theme, categorical_color,
                                direct_label, format_date_axis, save_figure)

logger = logging.getLogger("clo_atlas.macro.viz_regime")

REGIME_PATH = config.FINAL_DIR / "macro_rate_regime.parquet"
GROWTH_PATH = config.FINAL_DIR / "macro_duration_pain_growth.parquet"
DRAWDOWN_PATH = config.FINAL_DIR / "macro_duration_pain_drawdown.parquet"

REGIME_COLORS = {"ZIRP": WARM_GRAY[2], "Hiking": ACCENT, "Easing": WARM_GRAY[1], "Plateau": WARM_GRAY[0]}
CHART_YEARS_BACK = 35
FEATURED_ORDER = ["TLT", "AGG", "BKLN", "JAAA", "SHV"]


def viz_policy_rate_regime():
    apply_theme()
    regime = read_parquet(REGIME_PATH)
    if regime.empty:
        logger.warning("no rate-regime data; skipping viz_policy_rate_regime")
        return None
    regime["date"] = pd.to_datetime(regime["date"])
    cutoff = regime["date"].max() - pd.DateOffset(years=CHART_YEARS_BACK)
    regime = regime[regime["date"] >= cutoff].reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(10, 5))

    # Shade contiguous same-regime runs as spans so the plateau/hiking/ZIRP
    # story reads as bands, not a scatter of monthly ticks.
    regime["run_id"] = (regime["regime"] != regime["regime"].shift()).cumsum()
    for _, run in regime.groupby("run_id"):
        ax.axvspan(run["date"].iloc[0], run["date"].iloc[-1], color=REGIME_COLORS[run["regime"].iloc[0]],
                   alpha=0.28 if run["regime"].iloc[0] != "Hiking" else 0.35, lw=0, zorder=0)

    ax.plot(regime["date"], regime["fedfunds"], color="#1A1A1A", linewidth=1.8, zorder=2)

    current_regime = regime["regime"].iloc[-1]
    ax.annotate(f"Current: {current_regime.lower()} at {regime['fedfunds'].iloc[-1]:.2f}%",
                xy=(regime["date"].iloc[-1], regime["fedfunds"].iloc[-1]), xytext=(-140, 18),
                textcoords="offset points", fontsize=9.5, color=ACCENT, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1))

    ymin, ymax = ax.get_ylim()
    ax.set_ylim(ymin, ymax * 1.18)
    for label, color in REGIME_COLORS.items():
        ax.scatter([], [], marker="s", color=color, alpha=0.5, label=label)
    ax.legend(loc="upper left", ncol=4, fontsize=8.5, frameon=False)

    format_date_axis(ax, interval_months=36)
    ax.set_ylabel("Federal funds rate, effective (%)")
    png, svg = save_figure(
        fig, "viz_policy_rate_regime",
        headline="Rates went from zero to five percent and are not going back to zero.",
        subtitle=f"Effective federal funds rate, {regime['date'].iloc[0].year}-{regime['date'].iloc[-1].year}, shaded by rule-based regime "
                 f"(ZIRP ≤{config.MACRO_ZIRP_THRESHOLD_PCT}%; hiking/easing on a ±{config.MACRO_REGIME_ROC_THRESHOLD_PCT}pt 12-month change; plateau otherwise).",
        source="clo-atlas, from FRED (FEDFUNDS)",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_duration_bill():
    apply_theme()
    growth = read_parquet(GROWTH_PATH)
    if growth.empty:
        logger.warning("no duration-pain growth data; skipping viz_duration_bill")
        return None
    growth["date"] = pd.to_datetime(growth["date"])
    drawdown = read_parquet(DRAWDOWN_PATH) if DRAWDOWN_PATH.exists() else pd.DataFrame()

    fig, ax = plt.subplots(figsize=(9, 5.5))
    end_values = []
    for i, ticker in enumerate(FEATURED_ORDER):
        grp = growth[growth["ticker"] == ticker].sort_values("date")
        if grp.empty:
            continue
        color = categorical_color(0) if ticker in ("TLT", "AGG") else categorical_color(i + 1)
        ax.plot(grp["date"], grp["growth_of_100"], color=color,
                linewidth=2.4 if ticker in ("TLT", "AGG") else 1.6)
        end_values.append((grp["date"].iloc[-1], grp["growth_of_100"].iloc[-1], ticker, color))

    end_values.sort(key=lambda r: r[1])
    ymin, ymax = ax.get_ylim()
    min_gap = (ymax - ymin) * 0.04
    last_y = None
    for date, value, ticker, color in end_values:
        y = value if last_y is None else max(value, last_y + min_gap)
        note = ""
        if not drawdown.empty:
            row = drawdown[drawdown["ticker"] == ticker]
            if len(row):
                dd = row.iloc[0]["max_drawdown"] * 100
                recovered = row.iloc[0]["recovered"]
                note = f"  {dd:+.0f}%, {'recov.' if recovered else 'not recov.'}"
        direct_label(ax, date, y, f"{ticker}{note}", color=color)
        last_y = y

    ax.axhline(100, color=INK_MUTED, linewidth=0.8, linestyle=":", zorder=0)
    format_date_axis(ax, interval_months=6)
    ax.set_ylabel("Growth of $100")
    fig.subplots_adjust(right=0.82)
    png, svg = save_figure(
        fig, "viz_duration_bill",
        headline="Long duration paid the bill for the hiking cycle; floating-rate credit didn't.",
        subtitle=f"Cumulative total return, $100 invested {pd.Timestamp(growth['date'].min()).strftime('%b %Y')}, "
                  "long Treasuries (TLT) and the aggregate bond index (AGG) vs. floating-rate loans (BKLN), AAA CLOs (JAAA), and cash (SHV).",
        source="clo-atlas, from Yahoo Finance adjusted close via yfinance",
        notes="Trough/recovery status computed over the same window, as of the latest cached price date.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_policy_rate_regime()
    viz_duration_bill()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
