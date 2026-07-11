"""GDELT DOC 2.0 API (free, no key) — daily article-volume and average-tone
timelines for CLO-related queries. This is the backbone attention/tone
series for Section 6 v2: everything else (regulator alarm, StockTwits,
headlines) annotates this, not the other way around, because it's the only
corpus here with real daily resolution across many years.

GDELT publishes a strict "one request every 5 seconds" policy; this
project's sandboxed egress hit HTTP 429 even at 8-10s spacing during
development (2026-07-11), so config.RATE_LIMITS runs noticeably slower than
GDELT's own stated ceiling. A full run (len(GDELT_QUERIES) x 2 modes) takes
several minutes because of this — expected, not a bug.
"""
from __future__ import annotations

import datetime as dt
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.sentiment.scrape_gdelt")

OUT_PATH = config.INTERIM_DIR / "gdelt_timelines.parquet"
GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"


def _fetch_timeline(session: CachedSession, query: str, mode: str) -> pd.DataFrame:
    params = {"query": query, "mode": mode, "format": "json", "timespan": config.GDELT_TIMESPAN}
    try:
        result = session.get(GDELT_DOC_URL, params=params)
    except RuntimeError as exc:
        # CachedSession raises after exhausting retries rather than returning
        # a failed FetchResult; a persistent 429 here (observed repeatedly
        # from this project's sandboxed egress even with 5-retry exponential
        # backoff, 2026-07-11 — see docs/excluded_sources.md) must not take
        # down the rest of the query list.
        logger.warning("GDELT %s (%s) exhausted retries (%s); skipping this query", query, mode, exc)
        return pd.DataFrame()
    if result.status != 200:
        logger.warning("GDELT %s (%s) failed: status %d", query, mode, result.status)
        return pd.DataFrame()
    try:
        payload = result.json()
    except Exception as exc:
        logger.warning("GDELT %s (%s) returned non-JSON (%s) — likely a rate-limit notice, not an error page", query, mode, exc)
        return pd.DataFrame()

    series = payload.get("timeline", [])
    if not series:
        return pd.DataFrame()
    rows = []
    for point in series[0].get("data", []):
        rows.append({"query": query, "mode": mode, "date": point["date"], "value": point["value"]})
    df = pd.DataFrame(rows)
    if len(df):
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%dT%H%M%SZ", errors="coerce")
    return df


def scrape_gdelt_timelines(session: CachedSession, queries: list[str] | None = None) -> pd.DataFrame:
    queries = queries or config.GDELT_QUERIES
    frames = []
    for query in queries:
        vol = _fetch_timeline(session, query, "timelinevol")
        if len(vol):
            frames.append(vol)
            logger.info("GDELT volume %r: %d points", query, len(vol))
        tone = _fetch_timeline(session, query, "timelinetone")
        if len(tone):
            frames.append(tone)
            logger.info("GDELT tone %r: %d points", query, len(tone))
    if not frames:
        logger.warning("GDELT scrape returned nothing for any query — likely rate-limited from this environment")
        return pd.DataFrame(columns=["query", "mode", "date", "value"])
    return pd.concat(frames, ignore_index=True)


def run() -> pd.DataFrame:
    session = CachedSession()
    df = scrape_gdelt_timelines(session)
    if df.empty:
        logger.warning("no GDELT data scraped this run; downstream analysis will degrade gracefully")
        if OUT_PATH.exists():
            return pd.read_parquet(OUT_PATH)
        return df
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[GDELT_DOC_URL],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.sentiment.scrape_gdelt",
        notes=f"timelinevol (article volume) + timelinetone (avg tone) per query, timespan={config.GDELT_TIMESPAN}.",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
