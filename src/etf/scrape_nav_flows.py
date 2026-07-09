"""Daily NAV, market price, shares outstanding, and macro comparison series for
CLO ETFs (Section 1).

Price history comes from yfinance, which manages its own HTTP layer rather
than routing through src.common.http.CachedSession (yfinance's client isn't
built to be handed a foreign session) — since the project's raw-archiving
guarantee is "every response written to data/raw before parsing," this module
satisfies that itself by dumping each ticker's raw price CSV to
data/raw/yfinance/<ticker>.csv the moment it's fetched, before any tidying.

NAV and shares-outstanding are NOT available as a historical time series from
any free source found (issuer NAV-history pages sit behind the same JS walls
scrape_holdings.py hit; Yahoo only exposes a single current NAV/shares point,
not history). So this scraper takes a daily point-in-time snapshot on every
run and appends it to data/interim/etf_nav_snapshots.parquet, which means a
real premium/discount time series accretes from whenever this project starts
running regularly — it does not (and cannot honestly) back-fill NAV history
before that. This limitation is logged, not papered over.

FRED series (SOFR, 3m T-bill, HY OAS, EFFR) DO have full free history via the
fredgraph.csv endpoint, no API key required, fetched through CachedSession
like everything else that isn't yfinance.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging

import pandas as pd
import yfinance as yf

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.etf.scrape_nav_flows")

PRICES_OUT = config.INTERIM_DIR / "etf_prices.parquet"
SNAPSHOTS_OUT = config.INTERIM_DIR / "etf_nav_snapshots.parquet"
FRED_OUT = config.INTERIM_DIR / "fred_series.parquet"

ALL_PRICE_TICKERS = list(config.CLO_ETF_TICKERS.keys()) + config.ETF_COMPARISON_TICKERS
YFINANCE_RAW_DIR = config.RAW_DIR / "yfinance"


def _archive_yfinance_raw(ticker: str, df: pd.DataFrame) -> None:
    YFINANCE_RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    path = YFINANCE_RAW_DIR / f"{ticker}_{stamp}.csv"
    df.to_csv(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    logger.debug("archived raw yfinance pull for %s to %s (sha256:%s...)", ticker, path, digest)


def scrape_price_history(tickers: list[str] | None = None) -> pd.DataFrame:
    """Full daily OHLCV history per ticker back to inception, tidy long format."""
    tickers = tickers or ALL_PRICE_TICKERS
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
        raise RuntimeError("yfinance price scrape returned nothing for any ticker")
    return pd.concat(frames, ignore_index=True)


def scrape_nav_snapshot(tickers: list[str] | None = None) -> pd.DataFrame:
    """Point-in-time NAV/shares-outstanding snapshot for CLO ETFs, appended each run."""
    tickers = tickers or list(config.CLO_ETF_TICKERS.keys())
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
            "nav": info.get("navPrice"),
            "market_price": fast.get("lastPrice"),
            "shares_outstanding": fast.get("shares"),
            "trailing_dividend_yield": info.get("dividendYield"),
        })
    return pd.DataFrame(rows)


def scrape_fred_series(session: CachedSession, series: dict[str, str] | None = None) -> pd.DataFrame:
    series = series or config.FRED_SERIES
    frames = []
    for label, series_id in series.items():
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
        result = session.get(url, params={"id": series_id})
        if result.status != 200:
            logger.warning("FRED series %s (%s) failed: status %d", label, series_id, result.status)
            continue
        import io
        df = pd.read_csv(io.BytesIO(result.content))
        df.columns = ["date", "value"]
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["series"] = label
        frames.append(df)
        logger.info("FRED %s (%s): %d observations", label, series_id, len(df))
    if not frames:
        raise RuntimeError("FRED scrape returned nothing for any series")
    return pd.concat(frames, ignore_index=True)


def run() -> None:
    prices = scrape_price_history()
    write_parquet(prices, PRICES_OUT, Provenance(
        source_urls=["https://finance.yahoo.com (via yfinance)"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.etf.scrape_nav_flows.scrape_price_history",
        notes="Full OHLCV history back to each ticker's inception; re-running overwrites with a fresh full pull.",
    ))

    snapshot = scrape_nav_snapshot()
    if len(snapshot):
        if SNAPSHOTS_OUT.exists():
            existing = pd.read_parquet(SNAPSHOTS_OUT)
            combined = pd.concat([existing, snapshot], ignore_index=True)
            combined = combined.drop_duplicates(subset=["date", "ticker"], keep="last")
        else:
            combined = snapshot
        write_parquet(combined, SNAPSHOTS_OUT, Provenance(
            source_urls=["https://finance.yahoo.com (via yfinance, navPrice/fast_info)"],
            scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
            parser="src.etf.scrape_nav_flows.scrape_nav_snapshot",
            notes="Point-in-time snapshot appended each run; NAV history before this project's first run is not available from any free source found.",
        ))
        logger.info("NAV snapshot table now has %d rows across %d dates", len(combined), combined["date"].nunique())

    session = CachedSession()
    fred = scrape_fred_series(session)
    write_parquet(fred, FRED_OUT, Provenance(
        source_urls=[f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}" for sid in config.FRED_SERIES.values()],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.etf.scrape_nav_flows.scrape_fred_series",
    ))


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
