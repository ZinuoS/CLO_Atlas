"""yfinance `.get_news()` for the CLO ETF/CEF tickers — ticker-tagged
article metadata (title, publisher, timestamp, link), deduped into the same
headline corpus as scrape_news_rss.py. yfinance manages its own HTTP layer
(same rationale as src/etf/scrape_nav_flows.py), so raw responses are
archived to data/raw/yfinance/ manually before parsing rather than through
CachedSession.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging

import pandas as pd
import yfinance as yf

import config
from src.common.cache import Provenance, write_parquet

logger = logging.getLogger("clo_atlas.sentiment.scrape_yf_news")

OUT_PATH = config.INTERIM_DIR / "yf_ticker_news.parquet"
RAW_DIR = config.RAW_DIR / "yfinance_news"


def _archive_raw(ticker: str, payload: list[dict]) -> None:
    import json
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    path = RAW_DIR / f"{ticker}_{stamp}.json"
    path.write_text(json.dumps(payload))
    logger.debug("archived %s news raw to %s (sha256:%s...)", ticker, path,
                 hashlib.sha256(path.read_bytes()).hexdigest()[:12])


def scrape_ticker_news(tickers: list[str] | None = None) -> pd.DataFrame:
    tickers = tickers or config.YF_NEWS_TICKERS
    rows = []
    for ticker in tickers:
        try:
            news = yf.Ticker(ticker).get_news()
        except Exception as exc:
            logger.warning("%s: yfinance news fetch failed (%s), skipping", ticker, exc)
            continue
        if not news:
            logger.warning("%s: no news returned", ticker)
            continue
        _archive_raw(ticker, news)
        for item in news:
            content = item.get("content", item)
            provider = content.get("provider", {}) or {}
            rows.append({
                "ticker": ticker, "title": content.get("title", ""),
                "publisher": provider.get("displayName", ""),
                "pub_date": content.get("pubDate") or content.get("displayTime"),
                "link": (content.get("canonicalUrl") or {}).get("url", ""),
            })
        logger.info("%s: %d news items", ticker, len(news))
    if not rows:
        raise RuntimeError("yfinance news scrape returned nothing for any ticker")
    df = pd.DataFrame(rows).drop_duplicates(subset=["link"])
    df["pub_date"] = pd.to_datetime(df["pub_date"], errors="coerce", utc=True)
    return df


def run() -> pd.DataFrame:
    df = scrape_ticker_news()
    if OUT_PATH.exists():
        existing = pd.read_parquet(OUT_PATH)
        df = pd.concat([existing, df], ignore_index=True).drop_duplicates(subset=["link"])
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=["https://finance.yahoo.com (via yfinance .get_news())"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.sentiment.scrape_yf_news",
        notes="Ticker-tagged article metadata only; accretes across repeated runs since yfinance only serves recent news.",
    ))
    logger.info("yf_ticker_news.parquet now has %d rows", len(df))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
