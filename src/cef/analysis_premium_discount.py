"""CLO CEF premium/discount to book value (Section 2).

Uses bookValue as the NAV proxy (see scrape_prices_nav.py's docstring for
why the funds' own monthly NAV press releases aren't scraped here). Like
Section 1's ETF dislocation analysis, the composite sentiment index, regime
shading, and lead/lag-vs-ETF-discount pieces all need multi-date history
that accretes from repeated runs; the single-day cross-section is real today.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.cef.analysis_premium_discount")

SNAPSHOTS_PATH = config.INTERIM_DIR / "cef_bookvalue_snapshots.parquet"
ETF_DISLOCATION_PATH = config.FINAL_DIR / "etf_premium_discount_daily.parquet"

OUT_DAILY = config.FINAL_DIR / "cef_premium_discount_daily.parquet"
OUT_INDEX = config.FINAL_DIR / "cef_sentiment_index.parquet"
OUT_LEADLAG = config.FINAL_DIR / "cef_vs_etf_leadlag.parquet"

MIN_HISTORY = 30  # trading days needed before z-score regime shading is meaningful


def premium_discount_daily() -> pd.DataFrame:
    if not SNAPSHOTS_PATH.exists():
        logger.warning("no book-value snapshot history cached; premium_discount_daily will be empty")
        return pd.DataFrame(columns=["date", "ticker", "market_price", "book_value_per_share", "premium_discount"])
    snaps = read_parquet(SNAPSHOTS_PATH).dropna(subset=["market_price", "book_value_per_share"])
    snaps = snaps.copy()
    snaps["premium_discount"] = snaps["market_price"] / snaps["book_value_per_share"] - 1
    return snaps[["date", "ticker", "market_price", "book_value_per_share", "premium_discount"]].sort_values(["ticker", "date"])


def sentiment_index(daily: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight z-score of discounts across funds, per date. Needs
    rolling history per fund to compute a meaningful z-score (mean/std);
    below MIN_HISTORY observations this returns the raw cross-fund average
    discount instead, clearly distinguished by a `is_zscore` flag."""
    if daily.empty:
        return pd.DataFrame(columns=["date", "composite_value", "is_zscore"])
    n_dates = daily.groupby("ticker")["date"].nunique().max()
    if n_dates < MIN_HISTORY:
        logger.info("only %d date(s) of book-value history so far (<%d needed for z-scores); "
                     "reporting raw average discount instead", n_dates, MIN_HISTORY)
        avg = daily.groupby("date")["premium_discount"].mean().reset_index()
        avg = avg.rename(columns={"premium_discount": "composite_value"})
        avg["is_zscore"] = False
        return avg

    z = daily.copy()
    z["z"] = z.groupby("ticker")["premium_discount"].transform(lambda s: (s - s.mean()) / s.std())
    composite = z.groupby("date")["z"].mean().reset_index().rename(columns={"z": "composite_value"})
    composite["is_zscore"] = True
    return composite


def leadlag_vs_etf(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty or not ETF_DISLOCATION_PATH.exists():
        logger.warning("need both CEF and ETF discount history for lead/lag; returns empty until both accrete")
        return pd.DataFrame(columns=["date", "cef_avg_discount", "etf_avg_discount"])
    etf = read_parquet(ETF_DISLOCATION_PATH)
    cef_by_date = daily.groupby("date")["premium_discount"].mean()
    etf_by_date = etf.groupby("date")["premium_discount"].mean()
    merged = pd.DataFrame({"cef_avg_discount": cef_by_date, "etf_avg_discount": etf_by_date}).dropna()
    if len(merged) < 2:
        logger.info("lead/lag has <2 overlapping dates so far; any correlation claim here would be "
                     "meaningless — descriptive-only once enough history exists, per project ML doctrine")
    return merged.reset_index()


def run() -> dict[str, pd.DataFrame]:
    daily = premium_discount_daily()
    write_parquet(daily, OUT_DAILY, Provenance(parser="src.cef.analysis_premium_discount.premium_discount_daily", source_urls=[]))

    index = sentiment_index(daily)
    write_parquet(index, OUT_INDEX, Provenance(parser="src.cef.analysis_premium_discount.sentiment_index", source_urls=[]))

    leadlag = leadlag_vs_etf(daily)
    write_parquet(leadlag, OUT_LEADLAG, Provenance(parser="src.cef.analysis_premium_discount.leadlag_vs_etf", source_urls=[]))

    logger.info("daily=%d rows, sentiment_index=%d rows, leadlag=%d rows", len(daily), len(index), len(leadlag))
    return {"daily": daily, "index": index, "leadlag": leadlag}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
