"""Who owns U.S. CLO securities (Section 4).

Built from a single cited Fed snapshot (Dec 2018) — TO-VERIFY, not computed
in this repo. The chart says so directly in the subtitle rather than letting
it read as a live figure.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.official.viz_holders")

HOLDERS_PATH = config.FINAL_DIR / "clo_holder_composition.parquet"


def viz_holder_composition():
    apply_theme()
    df = read_parquet(HOLDERS_PATH)
    if df.empty:
        logger.warning("no holder composition data cached; skipping viz_holder_composition")
        return None
    df = df.sort_values("amount_usd_millions")

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.barh(df["investor_type"], df["amount_usd_millions"] / 1000, color=ACCENT)
    ax.set_xlabel("Domestic holdings ($ billions)")
    fig.subplots_adjust(left=0.3)

    citation = config.FED_CLO_HOLDER_CITATION
    png, svg = save_figure(
        fig, "viz_holder_composition",
        headline="Insurers, not banks, are the biggest domestic holders of U.S. CLO securities.",
        subtitle=f"TO-VERIFY — external figure, not computed in this repo. Domestic holdings of Cayman-issued "
                  f"U.S. CLO securities by investor type, as of {citation['as_of']}. No more recent free "
                  f"public breakdown has been located.",
        source=f"Federal Reserve FEDS Notes, \"{citation['source_title']}\"",
        notes=f"Full citation: {citation['source_url']}",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_holder_composition()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
