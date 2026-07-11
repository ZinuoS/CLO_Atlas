"""Google Trends via pytrends (Part C: where the asset class is going) —
the retail attention curve for CLO-adjacent search terms, weekly, 5 years.

pytrends manages its own HTTP against Google's undocumented trends
endpoint (not routed through CachedSession, same rationale as yfinance
elsewhere in this project); raw responses are archived manually.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging

import pandas as pd
from pytrends.request import TrendReq

import config
from src.common.cache import Provenance, write_parquet

logger = logging.getLogger("clo_atlas.future.scrape_trends")

OUT_PATH = config.INTERIM_DIR / "future_google_trends.parquet"
RAW_DIR = config.RAW_DIR / "google_trends"

TREND_QUERIES = ["CLO ETF", "JAAA", "private credit", "collateralized loan obligation"]
TIMEFRAME = "today 5-y"


def scrape_trends(queries: list[str] | None = None) -> pd.DataFrame:
    queries = queries or TREND_QUERIES
    pytrends = TrendReq(hl="en-US", tz=360)
    frames = []
    for query in queries:
        try:
            pytrends.build_payload([query], timeframe=TIMEFRAME)
            df = pytrends.interest_over_time()
        except Exception as exc:
            logger.warning("%s: pytrends fetch failed (%s), skipping", query, exc)
            continue
        if df is None or df.empty:
            logger.warning("%s: pytrends returned no data, skipping", query)
            continue
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        stamp = dt.date.today().isoformat()
        raw_path = RAW_DIR / f"{query.replace(' ', '_')}_{stamp}.csv"
        df.to_csv(raw_path)
        logger.debug("archived %s to %s (sha256:%s...)", query, raw_path, hashlib.sha256(raw_path.read_bytes()).hexdigest()[:12])

        tidy = df.reset_index().rename(columns={query: "interest", "date": "date"})[["date", "interest"]]
        tidy["query"] = query
        frames.append(tidy)
        logger.info("%s: %d weekly points", query, len(tidy))
    if not frames:
        raise RuntimeError("Google Trends scrape returned nothing for any query")
    return pd.concat(frames, ignore_index=True)


def run() -> pd.DataFrame:
    df = scrape_trends()
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=["https://trends.google.com (via pytrends)"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.future.scrape_trends",
        notes=f"Relative search interest (0-100), weekly, timeframe={TIMEFRAME}.",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
