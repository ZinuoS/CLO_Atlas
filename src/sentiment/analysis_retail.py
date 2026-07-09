"""Retail (Reddit) CLO sentiment (Section 6) — degrades gracefully. Depends
on scrape_reddit.py, which needs the user's own Reddit API credentials in
the environment (see that module's docstring and docs/excluded_sources.md).
Real, complete implementation; just no data cached in this run.
"""
from __future__ import annotations

import logging

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.sentiment.analysis_retail")

REDDIT_PATH = config.INTERIM_DIR / "reddit_mentions.parquet"
OUT_VOLUME = config.FINAL_DIR / "reddit_mention_volume.parquet"

_vader = SentimentIntensityAnalyzer()


def mention_volume_weekly() -> pd.DataFrame:
    if not REDDIT_PATH.exists():
        logger.warning("no Reddit data cached (needs REDDIT_* env vars — see scrape_reddit.py); "
                        "mention_volume_weekly is empty")
        return pd.DataFrame(columns=["week", "n_mentions", "n_unique_authors", "mean_vader"])
    df = read_parquet(REDDIT_PATH)
    if df.empty:
        return pd.DataFrame(columns=["week", "n_mentions", "n_unique_authors", "mean_vader"])
    df = df.copy()
    df["date"] = pd.to_datetime(df["created_utc"], unit="s")
    df["week"] = df["date"].dt.to_period("W").astype(str)
    df["vader"] = df.apply(lambda r: _vader.polarity_scores(f"{r['title']} {r['selftext']}")["compound"], axis=1)
    return df.groupby("week").agg(n_mentions=("id", "count"), n_unique_authors=("author", "nunique"),
                                    mean_vader=("vader", "mean")).reset_index()


def run() -> pd.DataFrame:
    df = mention_volume_weekly()
    write_parquet(df, OUT_VOLUME, Provenance(parser="src.sentiment.analysis_retail.mention_volume_weekly", source_urls=[]))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
