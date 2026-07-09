"""Crowding exhibits (Section 3): most widely held issuers, BDC portfolio
overlap.
"""
from __future__ import annotations

import logging

import matplotlib.pyplot as plt

import config
from src.common.cache import read_parquet
from src.common.style import ACCENT, apply_theme, save_figure

logger = logging.getLogger("clo_atlas.edgar.viz_crowding")

TOP_PATH = config.FINAL_DIR / "edgar_crowded_issuers.parquet"
OVERLAP_PATH = config.FINAL_DIR / "edgar_bdc_overlap_jaccard.parquet"


def viz_top_crowded_issuers():
    apply_theme()
    df = read_parquet(TOP_PATH)
    if df.empty:
        logger.warning("no crowded-issuer data cached; skipping viz_top_crowded_issuers")
        return None
    df = df.sort_values("n_filers").tail(15)

    fig, ax = plt.subplots(figsize=(8.5, 6))
    ax.barh(df["canonical_name"].str.slice(0, 35), df["n_filers"], color=ACCENT)
    ax.set_xlabel("Number of tracked BDCs holding this issuer (latest common period)")
    fig.subplots_adjust(left=0.34)

    png, svg = save_figure(
        fig, "viz_top_crowded_issuers",
        headline="A handful of borrowers show up across multiple lenders' books at once.",
        subtitle="Most widely co-held issuers across tracked BDCs, most recent shared reporting period.",
        source="clo-atlas, from SEC EDGAR BDC Schedules of Investment, entity-resolved",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def viz_bdc_overlap():
    apply_theme()
    df = read_parquet(OVERLAP_PATH)
    if df.empty:
        logger.warning("no BDC overlap data cached; skipping viz_bdc_overlap")
        return None
    df = df.copy()
    df["pair"] = df["filer_a"] + " – " + df["filer_b"]
    df = df.sort_values("jaccard")

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(df["pair"], df["jaccard"] * 100, color=ACCENT)
    ax.set_xlabel("Portfolio overlap (Jaccard similarity, %)")
    fig.subplots_adjust(left=0.22)

    png, svg = save_figure(
        fig, "viz_bdc_overlap",
        headline="BDC portfolios barely overlap — most lenders aren't in the same deals.",
        subtitle="Jaccard similarity of held-issuer sets between each pair of tracked BDCs with a shared reporting period.",
        source="clo-atlas, from SEC EDGAR BDC Schedules of Investment, entity-resolved",
    )
    logger.info("wrote %s / %s", png, svg)
    return png, svg


def run():
    viz_top_crowded_issuers()
    viz_bdc_overlap()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
