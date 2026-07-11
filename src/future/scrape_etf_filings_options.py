"""Listed options on CLO ETFs (Part C: market-maturation marker) — chain
existence and total open interest, via yfinance's option_chain wrapper
around OCC/exchange data.
"""
from __future__ import annotations

import datetime as dt
import logging

import pandas as pd
import yfinance as yf

import config
from src.common.cache import Provenance, write_parquet

logger = logging.getLogger("clo_atlas.future.scrape_etf_filings_options")

OUT_PATH = config.INTERIM_DIR / "future_etf_options.parquet"
OPTION_TICKERS = ["JAAA", "CLOZ", "CLOA", "CLOI", "JBBB"]


def scrape_options(tickers: list[str] | None = None) -> pd.DataFrame:
    tickers = tickers or OPTION_TICKERS
    rows = []
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            expirations = t.options
        except Exception as exc:
            logger.warning("%s: yfinance options fetch failed (%s), skipping", ticker, exc)
            continue
        if not expirations:
            rows.append({"ticker": ticker, "has_listed_options": False, "n_expirations": 0,
                         "total_open_interest": 0, "nearest_expiration": None})
            logger.info("%s: no listed options", ticker)
            continue
        total_oi = 0
        for exp in expirations:
            try:
                chain = t.option_chain(exp)
            except Exception:
                continue
            total_oi += chain.calls["openInterest"].fillna(0).sum() + chain.puts["openInterest"].fillna(0).sum()
        rows.append({"ticker": ticker, "has_listed_options": True, "n_expirations": len(expirations),
                     "total_open_interest": int(total_oi), "nearest_expiration": expirations[0]})
        logger.info("%s: %d expirations, %d total open interest", ticker, len(expirations), int(total_oi))
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    df = scrape_options()
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=["https://finance.yahoo.com (via yfinance option_chain)"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.future.scrape_etf_filings_options",
        notes="Point-in-time snapshot of open interest across current expirations, not a historical time series.",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
