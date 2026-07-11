"""Google News RSS per query (headline, source, timestamp — metadata only,
not paywalled article bodies) — a scoreable headline corpus in its own
right, and the source pool for the narrative-lifecycle analysis.

RSS is a public syndication feed with no login/paywall; this project only
reads title/link/published/source fields, never fetches the linked
article's full body text (which would cross into paywalled-content
territory for many of these publishers). Direct outlet RSS (Reuters
markets, CNBC, MarketWatch) is a documented enhancement path (each
publisher's own topic-feed URL pattern would need discovering individually)
not implemented this pass.
"""
from __future__ import annotations

import datetime as dt
import logging
import urllib.parse

import feedparser
import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.sentiment.scrape_news_rss")

OUT_PATH = config.INTERIM_DIR / "news_headlines.parquet"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"


def _fetch_query(session: CachedSession, query: str) -> pd.DataFrame:
    params = {"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    url = f"{GOOGLE_NEWS_RSS_URL}?{urllib.parse.urlencode(params)}"
    result = session.get(url)
    if result.status != 200:
        logger.warning("Google News RSS for %r failed: status %d", query, result.status)
        return pd.DataFrame()
    parsed = feedparser.parse(result.content)
    rows = []
    for entry in parsed.entries:
        source = entry.get("source", {}).get("title") if isinstance(entry.get("source"), dict) else None
        rows.append({
            "query": query, "title": entry.get("title", ""), "link": entry.get("link", ""),
            "published": entry.get("published", ""), "source": source,
        })
    return pd.DataFrame(rows)


def scrape_headlines(session: CachedSession, queries: list[str] | None = None) -> pd.DataFrame:
    queries = queries or config.NEWS_RSS_QUERIES
    frames = []
    for query in queries:
        df = _fetch_query(session, query)
        if len(df):
            df["published_dt"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
            frames.append(df)
            logger.info("Google News RSS %r: %d headlines", query, len(df))
    if not frames:
        logger.warning("Google News RSS scrape returned nothing for any query")
        return pd.DataFrame(columns=["query", "title", "link", "published", "source", "published_dt"])
    combined = pd.concat(frames, ignore_index=True)
    return combined.drop_duplicates(subset=["link"])


def run() -> pd.DataFrame:
    session = CachedSession()
    df = scrape_headlines(session)
    if df.empty:
        if OUT_PATH.exists():
            existing = pd.read_parquet(OUT_PATH)
            logger.warning("no headlines scraped this run; keeping %d previously cached", len(existing))
            return existing
        return df

    if OUT_PATH.exists():
        existing = pd.read_parquet(OUT_PATH)
        df = pd.concat([existing, df], ignore_index=True).drop_duplicates(subset=["link"])

    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[GOOGLE_NEWS_RSS_URL],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.sentiment.scrape_news_rss",
        notes="Headline/source/timestamp metadata only, deduped by link; accretes across repeated runs "
              "(poll-forward daily via a scheduled `make news` target), since Google News RSS only serves current results.",
    ))
    logger.info("news_headlines.parquet now has %d rows", len(df))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
