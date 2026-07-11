"""Litigation-intensity exhibit (Part C): docket counts by year for the
LME/creditor-conflict era's public query terms.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, WARM_GRAY, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.future.viz_legal")

INTENSITY_PATH = config.FINAL_DIR / "legal_regime_litigation_intensity.parquet"


def viz_litigation_intensity():
    apply_theme()
    df = read_parquet(INTENSITY_PATH)
    if df.empty:
        logger.warning("no litigation-intensity data; skipping viz_litigation_intensity")
        return None

    years = sorted(df["year"].unique())
    queries = sorted(df["query"].unique())
    fig, ax = plt.subplots(figsize=(9, 5))
    bottom = [0] * len(years)
    for i, query in enumerate(queries):
        color = ACCENT if i == 0 else WARM_GRAY[i % len(WARM_GRAY)]
        heights = [df[(df["year"] == y) & (df["query"] == query)]["n_dockets"].sum() for y in years]
        ax.bar([str(y) for y in years], heights, bottom=bottom, color=color, label=query, width=0.6)
        bottom = [b + h for b, h in zip(bottom, heights)]

    ax.set_ylabel("Dockets filed (first page per query)")
    ax.legend(loc="upper left", fontsize=7.5, frameon=False)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    png, svg = save_figure(
        fig, "viz_litigation_intensity",
        headline="Creditor-conflict litigation (uptier, drop-down, LME) has a real, growing docket record.",
        subtitle="CourtListener/RECAP docket counts by year for public LME-era query terms.",
        source="clo-atlas, from CourtListener (courtlistener.com/api)",
        notes="First page of results per query (up to 20), not exhaustive; the LME-vocabulary and realized-downgrade "
              "links this exhibit was meant to join against are unavailable (Section 5's presale/ratings corpora are empty).",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_litigation_intensity()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
