"""Vintage cohort downgrade curves (Section 5) — degrades gracefully.
Depends on analysis_vintage.py, empty because scrape_actions.py is stubbed
(see docs/excluded_sources.md).
"""
from __future__ import annotations

import logging

import config
from src.common.cache import read_parquet

logger = logging.getLogger("clo_atlas.ratings.viz_vintage")

VINTAGE_PATH = config.FINAL_DIR / "ratings_vintage_cohorts.parquet"


def viz_vintage_downgrade_curves():
    df = read_parquet(VINTAGE_PATH)
    if df.empty:
        logger.warning("no vintage cohort data available (S&P/Fitch gated — see docs/excluded_sources.md); "
                        "skipping viz_vintage_downgrade_curves")
        return None
    logger.warning("vintage data present but no chart implemented yet")
    return None


def run():
    viz_vintage_downgrade_curves()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
