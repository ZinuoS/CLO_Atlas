"""Scenario-monitoring map as a clean table-graphic (Part C, closing
slide) — a watchlist, not a forecast.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, INK, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.future.viz_watchlist")

WATCHLIST_PATH = config.FINAL_DIR / "scenarios_watchlist.parquet"

_ARROW = {"up": "UP", "down": "DOWN", "flat-to-up": "FLAT/UP"}


def _wrap(text: str, width: int = 55) -> str:
    import textwrap
    return "\n".join(textwrap.wrap(text, width=width))


def viz_scenario_watchlist():
    apply_theme()
    df = read_parquet(WATCHLIST_PATH)
    if df.empty:
        logger.warning("no scenario-watchlist data; skipping viz_scenario_watchlist")
        return None

    fig, ax = plt.subplots(figsize=(13, 0.85 * len(df) + 1.4))
    ax.axis("off")
    rows = [[_wrap(row["scenario"], 22), row["series"], _ARROW.get(row["expected_direction"], row["expected_direction"]), _wrap(row["why"], 60)]
            for _, row in df.iterrows()]
    table = ax.table(cellText=rows, colLabels=["Scenario", "Series to watch", "Expected\nfirst move", "Why"],
                      loc="center", cellLoc="left", colWidths=[0.16, 0.22, 0.1, 0.52])
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1, 2.6)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor(WARM_GRAY[3])
        if r == 0:
            cell.set_text_props(fontweight="bold", color=INK)
            cell.set_facecolor(WARM_GRAY[3])
        else:
            cell.set_facecolor("white")
            if c == 2:
                cell.set_text_props(color=ACCENT, fontweight="bold", ha="center")

    png, svg = save_figure(
        fig, "viz_scenario_watchlist",
        headline="Not a forecast — a monitoring map of which of this project's own series would move first.",
        subtitle="Three macro scenarios, each paired with the already-built series expected to move first and in which direction.",
        source="clo-atlas synthesis, referencing series built across the macro/CEF/sentiment sections",
        notes="A hypothesis to monitor, not a backtested or fitted prediction.",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_scenario_watchlist()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
