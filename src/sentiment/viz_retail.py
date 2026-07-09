"""Retail (Reddit) sentiment exhibits (Section 6) — degrades gracefully.
Depends on analysis_retail.py, empty because scrape_reddit.py needs the
user's own Reddit API credentials (see docs/excluded_sources.md).
"""
from __future__ import annotations

import logging

import config
from src.common.cache import read_parquet

logger = logging.getLogger("clo_atlas.sentiment.viz_retail")

VOLUME_PATH = config.FINAL_DIR / "reddit_mention_volume.parquet"


def viz_reddit_mentions_vs_etf_aum():
    df = read_parquet(VOLUME_PATH)
    if df.empty:
        logger.warning("no Reddit data available (needs REDDIT_* env vars — see docs/excluded_sources.md); "
                        "skipping viz_reddit_mentions_vs_etf_aum")
        return None
    logger.warning("Reddit data present but no chart implemented yet")
    return None


def run():
    viz_reddit_mentions_vs_etf_aum()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
