"""Typical AAA attachment point, reinvestment length, WAL covenant drift
over time from presale text/tables (Section 5) — degrades gracefully to
empty. Depends on scrape_presales.py, which is stubbed — see
docs/excluded_sources.md and src/ratings/scrape_presales.py's docstring.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.ratings import scrape_presales

logger = logging.getLogger("clo_atlas.ratings.analysis_structure_drift")

OUT_PATH = config.FINAL_DIR / "ratings_structure_drift.parquet"


def structure_drift() -> pd.DataFrame:
    raw = scrape_presales.run()
    if raw.empty:
        logger.warning("no presale corpus available; structure_drift is empty")
        return pd.DataFrame(columns=["date", "deal", "aaa_attachment_pct", "reinvestment_period_years",
                                       "wal_years", "extraction_confidence"])
    return raw


def run() -> pd.DataFrame:
    df = structure_drift()
    write_parquet(df, OUT_PATH, Provenance(parser="src.ratings.analysis_structure_drift.structure_drift", source_urls=[]))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
