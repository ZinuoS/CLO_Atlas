"""Income exhibits (appendix/Q&A material): same-rating spread comparison,
carry-per-unit-duration, and the CLO AAA price-dispersion proxy.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.macro.viz_income")

SPREAD_PATH = config.FINAL_DIR / "macro_spread_comparison.parquet"
CARRY_PATH = config.FINAL_DIR / "macro_carry_per_duration.parquet"
DISPERSION_PATH = config.FINAL_DIR / "macro_aaa_dispersion_proxy.parquet"


def viz_spread_comparison():
    apply_theme()
    df = read_parquet(SPREAD_PATH)
    if df.empty:
        logger.warning("no spread-comparison data; skipping viz_spread_comparison")
        return None

    fig, ax = plt.subplots(figsize=(7.5, 4))
    colors = [WARM_GRAY[1]] * len(df)
    ax.scatter(df["oas_pct"], range(len(df)), s=160, color=colors, zorder=3)
    for i, row in df.iterrows():
        ax.plot([0, row["oas_pct"]], [i, i], color=WARM_GRAY[3], lw=1.5, zorder=1)
        ax.annotate(f"{row['oas_pct']:.2f}pp", xy=(row["oas_pct"], i), xytext=(10, 0),
                    textcoords="offset points", va="center", fontsize=9.5, color=INK)
    ax.set_yticks(range(len(df)))
    ax.set_yticklabels(df["market"], fontsize=10)
    ax.set_xlabel("Option-adjusted spread over risk-free (percentage points)")
    fig.subplots_adjust(left=0.24)
    as_of = df["as_of"].max()
    png, svg = save_figure(
        fig, "viz_spread_comparison",
        headline="Spread compensation rises steadily from AAA to high yield — the ladder investors already know.",
        subtitle=f"ICE BofA option-adjusted spread by rating bucket, as of {as_of.date() if hasattr(as_of, 'date') else as_of}.",
        source="clo-atlas, from FRED (ICE BofA OAS series)",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_carry_per_duration():
    apply_theme()
    df = read_parquet(CARRY_PATH)
    if df.empty:
        logger.warning("no carry-per-duration data; skipping viz_carry_per_duration")
        return None

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    colors = [ACCENT if t == "JAAA" else WARM_GRAY[1] for t in df["ticker"]]
    bars = ax.bar(df["ticker"], df["carry_per_duration"], color=colors, width=0.55)
    for bar, (_, row) in zip(bars, df.iterrows()):
        ax.annotate(f"{row['yield_pct']*100:.1f}% / {row['effective_duration_years']:.2f}yr dur.",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()), xytext=(0, 6),
                    textcoords="offset points", ha="center", fontsize=8.5, color=INK)
    ax.set_ylabel("Yield ÷ effective duration")
    png, svg = save_figure(
        fig, "viz_carry_per_duration",
        headline="Per unit of duration risk, JAAA pays for the wait; AGG barely does.",
        subtitle="Yield divided by effective duration, by fund. Yield definitions differ by issuer (labeled per bar) — not a like-for-like blend.",
        source="clo-atlas, from each fund's own overview page (iShares; Janus Henderson)",
        notes="JAAA's effective duration (0.04 yrs) is floored at 0.05 before dividing, so the ratio reflects a near-zero- but not literally zero-duration instrument.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_aaa_dispersion_proxy():
    apply_theme()
    df = read_parquet(DISPERSION_PATH)
    if df.empty:
        logger.warning("no AAA dispersion data; skipping viz_aaa_dispersion_proxy")
        return None

    fig, ax = plt.subplots(figsize=(6, 4))
    row = df.iloc[-1]
    ax.errorbar([0], [row["median_price"]], yerr=[[row["median_price"] - row["p10"]], [row["p90"] - row["median_price"]]],
                fmt="o", color=ACCENT, markersize=12, capsize=8, linewidth=2)
    ax.set_xlim(-1, 1)
    ax.set_xticks([])
    ax.set_ylabel("AAA CLO mark (price)")
    ax.annotate(f"median {row['median_price']:.2f}\np10-p90: {row['p10']:.2f}-{row['p90']:.2f}",
                xy=(0, row["median_price"]), xytext=(20, 0), textcoords="offset points", fontsize=9.5, va="center")
    png, svg = save_figure(
        fig, "viz_aaa_dispersion_proxy",
        headline="AAA CLO marks cluster tightly around par — a price-based stand-in for a spread series that doesn't exist here.",
        subtitle=f"Cross-sectional AAA CLO ETF holdings mark dispersion, {row['date']}. A discount-margin series was not available; "
                 "this is a price-based proxy, not a spread.",
        source="clo-atlas, from Section 1 ETF holdings",
        notes="Single scrape date available — Section 1's holdings history has not yet accreted a second snapshot.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_spread_comparison()
    viz_carry_per_duration()
    viz_aaa_dispersion_proxy()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
