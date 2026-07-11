"""Daily prices/yields for the listed preferreds and baby bonds of OXLC and
ECC (Section 2 deep-dive) — the funds' observable marginal cost of capital.

Tickers in config.CLO_CEF_PREFERRED_TICKERS were individually verified
resolvable via yfinance 2026-07-11 (each issuer follows a <BASE><SERIES
LETTER> convention, but not every guessed letter is real/still listed —
ECCD/ECCF/ECCX/ECCW returned no data and are excluded, not fabricated).
Current yield is computed as $25 stated liquidation preference x coupon /
price — the standard approximation for exchange-listed term preferred/baby
bonds, not a yield-to-maturity/worst calculation (which would need the
exact call schedule, not always disclosed cleanly).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging

import pandas as pd
import yfinance as yf

import config
from src.common.cache import Provenance, write_parquet

logger = logging.getLogger("clo_atlas.cef.scrape_preferreds")

OUT_PATH = config.INTERIM_DIR / "cef_preferred_prices.parquet"
OUT_SPLITS_PATH = config.INTERIM_DIR / "cef_stock_splits.parquet"
YFINANCE_RAW_DIR = config.RAW_DIR / "yfinance"


def _archive_raw(ticker: str, df: pd.DataFrame) -> None:
    YFINANCE_RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    path = YFINANCE_RAW_DIR / f"{ticker}_{stamp}.csv"
    df.to_csv(path)
    logger.debug("archived %s to %s (sha256:%s...)", ticker, path, hashlib.sha256(path.read_bytes()).hexdigest()[:12])


def scrape_preferred_prices(tickers_by_fund: dict[str, list[str]] | None = None) -> pd.DataFrame:
    tickers_by_fund = tickers_by_fund or config.CLO_CEF_PREFERRED_TICKERS
    frames = []
    for fund, tickers in tickers_by_fund.items():
        for ticker in tickers:
            try:
                raw = yf.download(ticker, period="max", auto_adjust=False, progress=False)
            except Exception as exc:
                logger.warning("%s: yfinance download failed (%s), skipping", ticker, exc)
                continue
            if raw is None or raw.empty:
                logger.warning("%s: yfinance returned no price data, skipping", ticker)
                continue
            _archive_raw(ticker, raw)
            raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
            tidy = raw.reset_index().rename(columns={"Date": "date", "Close": "close", "Adj Close": "adj_close"})
            tidy["ticker"] = ticker
            tidy["fund"] = fund
            frames.append(tidy[["date", "ticker", "fund", "close", "adj_close"]])
            logger.info("%s (%s): %d days of price history", ticker, fund, len(tidy))
    if not frames:
        raise RuntimeError("preferred-price scrape returned nothing for any ticker")
    return pd.concat(frames, ignore_index=True)


def scrape_stock_splits(tickers: list[str] | None = None) -> pd.DataFrame:
    """Corporate-action split history for the common tickers, e.g. OXLC's
    2025-09-08 1-for-5 reverse split. Needed because Yahoo's historical
    "Close" (not just "Adj Close") is retroactively split-adjusted once a
    split occurs — comparing an un-rescaled pre-split NAV disclosure
    against a post-split-adjusted historical close silently produces a
    nonsense multiple-of-par "premium" (discovered exactly this way, not
    assumed — see analysis_capital_machine.py's docstring)."""
    tickers = tickers or config.CLO_CEF_TICKERS
    rows = []
    for ticker in tickers:
        try:
            splits = yf.Ticker(ticker).splits
        except Exception as exc:
            logger.warning("%s: yfinance splits fetch failed (%s), skipping", ticker, exc)
            continue
        for split_date, ratio in splits.items():
            rows.append({"ticker": ticker, "split_date": pd.Timestamp(split_date).tz_localize(None), "ratio": float(ratio)})
        logger.info("%s: %d recorded split(s)", ticker, len(splits))
    return pd.DataFrame(rows, columns=["ticker", "split_date", "ratio"])


def run() -> pd.DataFrame:
    df = scrape_preferred_prices()
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=["https://finance.yahoo.com (via yfinance)"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.cef.scrape_preferreds",
        notes="Tickers verified individually resolvable; guessed series letters with no real price data excluded.",
    ))

    splits = scrape_stock_splits()
    write_parquet(splits, OUT_SPLITS_PATH, Provenance(
        source_urls=["https://finance.yahoo.com (via yfinance Ticker.splits)"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.cef.scrape_preferreds.scrape_stock_splits",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
