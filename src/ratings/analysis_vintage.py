"""Downgrade rates by deal vintage cohort (Section 5) — degrades gracefully
to empty. Depends on scrape_actions.py, which is stubbed — see
docs/excluded_sources.md and src/ratings/scrape_actions.py's docstring.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.ratings import scrape_actions

logger = logging.getLogger("clo_atlas.ratings.analysis_vintage")

OUT_PATH = config.FINAL_DIR / "ratings_vintage_cohorts.parquet"


def vintage_cohort_curves() -> pd.DataFrame:
    raw = scrape_actions.run()
    if raw.empty:
        logger.warning("no rating-action data available; vintage_cohort_curves is empty")
        return pd.DataFrame(columns=["vintage", "months_since_issuance", "cumulative_downgrade_rate"])
    return raw


def run() -> pd.DataFrame:
    df = vintage_cohort_curves()
    write_parquet(df, OUT_PATH, Provenance(parser="src.ratings.analysis_vintage.vintage_cohort_curves", source_urls=[]))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
