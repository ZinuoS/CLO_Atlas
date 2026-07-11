"""Market-maturation scorecard exhibit (Part C, closing slide): the one
genuinely multi-year input (Google Trends retail attention, indexed) as a
line chart, plus the current-state snapshot metrics as a table-graphic —
prefer indexed small multiples over a radar per the project's chart-form
doctrine; a radar isn't used here since most inputs aren't multi-year series.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK, WARM_GRAY, apply_theme, categorical_color, save_figure

logger = logging.getLogger("clo_atlas.future.viz_scorecard")

TRENDS_PATH = config.FINAL_DIR / "maturation_scorecard_trends_indexed.parquet"
SNAPSHOT_PATH = config.FINAL_DIR / "maturation_scorecard_snapshot.parquet"


def viz_attention_indexed():
    apply_theme()
    df = read_parquet(TRENDS_PATH)
    if df.empty:
        logger.warning("no indexed-trends data; skipping viz_attention_indexed")
        return None
    df["date"] = df["date"] if df["date"].dtype == "O" else df["date"]

    fig, ax = plt.subplots(figsize=(9, 5))
    for i, (query, grp) in enumerate(df.groupby("query")):
        ax.plot(grp["date"], grp["index_100"], color=categorical_color(i), label=query, linewidth=1.6)
    ax.axhline(100, color=INK, linewidth=0.8, linestyle=":")
    ax.set_ylabel("Search interest, indexed to 100 at first observation")
    ax.legend(loc="upper left", fontsize=8, frameon=False)
    png, svg = save_figure(
        fig, "viz_attention_indexed",
        headline="Retail search attention to CLOs and private credit has grown, not faded.",
        subtitle="Google Trends relative search interest, indexed to 100 at each query's earliest observed week, 5-year window.",
        source="clo-atlas, from Google Trends (via pytrends)",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_scorecard_table():
    apply_theme()
    df = read_parquet(SNAPSHOT_PATH)
    if df.empty:
        logger.warning("no scorecard snapshot data; skipping viz_scorecard_table")
        return None

    fig, ax = plt.subplots(figsize=(9, 0.6 * len(df) + 1.2))
    ax.axis("off")
    rows = [[row["metric"], f"{row['value']:,.0f}" if isinstance(row["value"], (int, float)) else str(row["value"]),
             str(row["unit"]), str(row["as_of"])] for _, row in df.iterrows()]
    table = ax.table(cellText=rows, colLabels=["Metric", "Value", "Unit", "As of"], loc="center", cellLoc="left")
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.8)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor(WARM_GRAY[3])
        if r == 0:
            cell.set_text_props(fontweight="bold", color=INK)
            cell.set_facecolor(WARM_GRAY[3])
        else:
            cell.set_facecolor("white")

    png, svg = save_figure(
        fig, "viz_scorecard_table",
        headline="Every measurable dimension of market maturity checked here points the same direction.",
        subtitle="Current-state snapshot across ETF scale, secondary trading, derivatives, and holder diversification.",
        source="clo-atlas, combining Sections 1/4 and this project's Part C scrapers",
        notes="A snapshot, not an indexed multi-year trend — most inputs are single-date series in this project so far.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_attention_indexed()
    viz_scorecard_table()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
