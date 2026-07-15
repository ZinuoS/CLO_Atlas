"""Daily prices and a NAV proxy for listed CLO closed-end funds (Section 2).

Price history: yfinance, same pattern as src/etf/scrape_nav_flows.py (raw
CSV archived to data/raw/yfinance/ before parsing).

NAV: these tickers are classified as plain EQUITY on Yahoo (not FUND), so
`navPrice` — which worked for the Section 1 ETFs — isn't populated. The one
NAV-adjacent figure Yahoo does expose is `bookValue` (book value per share
from the latest balance sheet), which for a CLO-equity-heavy CEF is a real
if imperfect proxy: it moves with quarterly financials, not the fund's own
monthly NAV estimate press releases. Those press releases/8-Ks are a
documented enhancement path (scrape_filings.py already resolves each fund's
CIK, so pulling 8-K text for "net asset value" mentions is the natural next
step) but are not implemented here — bookValue is used and clearly labeled
as a proxy, not silently treated as NAV.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging

import pandas as pd
import yfinance as yf

import config
from src.common.cache import Provenance, write_parquet

logger = logging.getLogger("clo_atlas.cef.scrape_prices_nav")

PRICES_OUT = config.INTERIM_DIR / "cef_prices.parquet"
SNAPSHOTS_OUT = config.INTERIM_DIR / "cef_bookvalue_snapshots.parquet"
DISTRIBUTIONS_OUT = config.INTERIM_DIR / "cef_distributions.parquet"
YFINANCE_RAW_DIR = config.RAW_DIR / "yfinance"


def _archive_yfinance_raw(ticker: str, df: pd.DataFrame) -> None:
    YFINANCE_RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    path = YFINANCE_RAW_DIR / f"cef_{ticker}_{stamp}.csv"
    df.to_csv(path)
    hashlib.sha256(path.read_bytes()).hexdigest()


def scrape_price_history(tickers: list[str] | None = None) -> pd.DataFrame:
    tickers = tickers or config.CLO_CEF_TICKERS
    frames = []
    for ticker in tickers:
        try:
            raw = yf.download(ticker, period="max", auto_adjust=False, progress=False)
        except Exception as exc:
            logger.warning("%s: yfinance download failed (%s), skipping", ticker, exc)
            continue
        if raw is None or raw.empty:
            logger.warning("%s: yfinance returned no price data, skipping", ticker)
            continue
        _archive_yfinance_raw(ticker, raw)
        raw.columns = [c[0] if isinstance(c, tuple) else c for c in raw.columns]
        tidy = raw.reset_index().rename(columns={
            "Date": "date", "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Adj Close": "adj_close", "Volume": "volume",
        })
        tidy["ticker"] = ticker
        frames.append(tidy[["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]])
        logger.info("%s: %d days of price history (%s to %s)", ticker, len(tidy),
                    tidy["date"].min().date(), tidy["date"].max().date())
    if not frames:
        raise RuntimeError("yfinance price scrape returned nothing for any CEF ticker")
    return pd.concat(frames, ignore_index=True)


def scrape_bookvalue_snapshot(tickers: list[str] | None = None) -> pd.DataFrame:
    tickers = tickers or config.CLO_CEF_TICKERS
    rows = []
    today = dt.date.today()
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.get_info()
            fast = t.fast_info
        except Exception as exc:
            logger.warning("%s: yfinance info/fast_info failed (%s), skipping snapshot", ticker, exc)
            continue
        rows.append({
            "date": today,
            "ticker": ticker,
            "book_value_per_share": info.get("bookValue"),
            "market_price": fast.get("lastPrice"),
            "price_to_book": info.get("priceToBook"),
            "trailing_dividend_yield": info.get("dividendYield"),
            # Current share count, same info payload -- lets a caller combine
            # this with a fund-level total-net-assets figure (e.g. from the
            # latest NPORT-P filing) for a NAV-per-share estimate fresher
            # than a fund's own periodic "financial update" disclosures.
            "shares_outstanding": info.get("sharesOutstanding"),
        })
    return pd.DataFrame(rows)


def scrape_distributions(tickers: list[str] | None = None) -> pd.DataFrame:
    """Declared-dividend history via yfinance — real and complete, unlike the
    price-based NAV proxy above; Yahoo carries full corporate-action history
    even for tickers it classifies as plain equity."""
    tickers = tickers or config.CLO_CEF_TICKERS
    frames = []
    for ticker in tickers:
        try:
            divs = yf.Ticker(ticker).dividends
        except Exception as exc:
            logger.warning("%s: dividend history fetch failed (%s), skipping", ticker, exc)
            continue
        if divs is None or divs.empty:
            logger.warning("%s: no dividend history returned, skipping", ticker)
            continue
        tidy = divs.reset_index()
        tidy.columns = ["ex_date", "amount"]
        tidy["ticker"] = ticker
        frames.append(tidy)
        logger.info("%s: %d distribution events (%s to %s)", ticker, len(tidy),
                    tidy["ex_date"].min().date(), tidy["ex_date"].max().date())
    if not frames:
        raise RuntimeError("yfinance distribution scrape returned nothing for any CEF ticker")
    return pd.concat(frames, ignore_index=True)


BETA_COMPARISON_TICKERS = ["SPY", "HYG"]


def run() -> None:
    prices = scrape_price_history(config.CLO_CEF_TICKERS + BETA_COMPARISON_TICKERS)
    write_parquet(prices, PRICES_OUT, Provenance(
        source_urls=["https://finance.yahoo.com (via yfinance)"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.cef.scrape_prices_nav.scrape_price_history",
    ))

    snapshot = scrape_bookvalue_snapshot()
    if len(snapshot):
        if SNAPSHOTS_OUT.exists():
            existing = pd.read_parquet(SNAPSHOTS_OUT)
            combined = snapshot if existing.empty else pd.concat([existing, snapshot], ignore_index=True)
            combined = combined.drop_duplicates(subset=["date", "ticker"], keep="last")
        else:
            combined = snapshot
        write_parquet(combined, SNAPSHOTS_OUT, Provenance(
            source_urls=["https://finance.yahoo.com (via yfinance, bookValue/priceToBook)"],
            scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
            parser="src.cef.scrape_prices_nav.scrape_bookvalue_snapshot",
            notes="bookValue is a quarterly accounting proxy for NAV, not the fund's own published NAV estimate.",
        ))
        logger.info("book-value snapshot table now has %d rows across %d dates",
                    len(combined), combined["date"].nunique())

    distributions = scrape_distributions()
    write_parquet(distributions, DISTRIBUTIONS_OUT, Provenance(
        source_urls=["https://finance.yahoo.com (via yfinance, dividend history)"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.cef.scrape_prices_nav.scrape_distributions",
    ))


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
