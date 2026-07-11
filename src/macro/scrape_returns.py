"""Total-return proxy extras for the macro opener (slides 1-2).

Section 1 (src/etf/scrape_nav_flows.py) already has full adjusted-close
history for JAAA/JBBB/AGG/HYG/BKLN/LQD/SHV in data/interim/etf_prices.parquet
— reused as-is by analysis_regime.py rather than re-scraped here. This module
only fetches the two tickers the macro section needs that Section 1 doesn't:
TLT (long Treasury duration pain) and SPY (broad-market context).

ICI weekly money-market fund AUM (the "cash on the sidelines" demand-side
kicker) was investigated and stubbed: the stable weekly download that page
links to is a plain HTML redirect wrapper, and the underlying dated
`mm_summary_data_<year>.xls` files are legacy binary BIFF8 workbooks that
need `xlrd`, which is not in requirements.txt (see docs/excluded_sources.md —
adding a dependency needs a check-in first, and this is an appendix-tier
exhibit, not one of the two synthesized slides).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import re

import pandas as pd
import yfinance as yf

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.macro.scrape_returns")

OUT_PATH = config.INTERIM_DIR / "macro_returns_extra.parquet"
CHARACTERISTICS_OUT_PATH = config.INTERIM_DIR / "macro_fund_characteristics.parquet"
YFINANCE_RAW_DIR = config.RAW_DIR / "yfinance"

EXTRA_TICKERS = ["TLT", "SPY"]

# Fund overview pages (not the JS-gated full-holdings pages Section 1 already
# ran into) for the carry-per-unit-duration exhibit. Verified server-rendered
# 2026-07-11: iShares embeds a "label"/"formattedValue" JSON pair per
# characteristic; Janus Henderson renders a plain HTML characteristics table.
_ISHARES_PAGES = {
    "AGG": "https://www.ishares.com/us/products/239458/ishares-core-total-us-bond-market-etf",
    "LQD": "https://www.ishares.com/us/products/239566/ishares-iboxx-investment-grade-corporate-bond-etf",
    "HYG": "https://www.ishares.com/us/products/239565/ishares-iboxx-high-yield-corporate-bond-etf",
}
_JANUS_PAGES = {
    "JAAA": "https://www.janushenderson.com/en-us/advisor/product/jaaa-aaa-clo-etf/",
}


def _parse_ishares_characteristics(html: str) -> dict[str, str]:
    """Extract {label: formattedValue} for Effective Duration / Average Yield
    to Maturity from an iShares product page's embedded JSON. HTML-entity
    quoting (`&quot;`) is used in the raw response, not literal `"`."""
    out = {}
    for label in ("Effective Duration", "Average Yield to Maturity"):
        pattern = rf'&quot;label&quot;:&quot;{re.escape(label)}&quot;.{{0,300}}?formattedValue&quot;:&quot;([^&]*)&quot;'
        m = re.search(pattern, html)
        if m:
            out[label] = m.group(1)
    return out


def _parse_janus_characteristics(html: str) -> dict[str, str]:
    """Extract {label: value} for Effective Duration / Yield to Worst from
    Janus Henderson's plain HTML characteristics table."""
    out = {}
    for label in ("Effective Duration", "Yield to Worst"):
        pattern = rf'<strong>{re.escape(label)}</strong>.{{0,120}}?<td>([^<]*)</td>'
        m = re.search(pattern, html, re.DOTALL)
        if m:
            out[label] = m.group(1).strip()
    return out


def _to_years(value: str | None) -> float | None:
    if not value:
        return None
    m = re.search(r"[-0-9.]+", value)
    return float(m.group(0)) if m else None


def _to_pct(value: str | None) -> float | None:
    if not value:
        return None
    m = re.search(r"[-0-9.]+", value)
    return float(m.group(0)) / 100 if m else None


def scrape_fund_characteristics(session: CachedSession) -> pd.DataFrame:
    rows = []
    for ticker, url in _ISHARES_PAGES.items():
        result = session.get(url)
        if result.status != 200:
            logger.warning("%s: fund-characteristics page failed (status %d), skipping", ticker, result.status)
            continue
        parsed = _parse_ishares_characteristics(result.text())
        rows.append({
            "ticker": ticker, "effective_duration_years": _to_years(parsed.get("Effective Duration")),
            "yield_pct": _to_pct(parsed.get("Average Yield to Maturity")), "yield_label": "Average Yield to Maturity",
        })
        logger.info("%s: duration=%s, yield=%s", ticker, parsed.get("Effective Duration"), parsed.get("Average Yield to Maturity"))

    for ticker, url in _JANUS_PAGES.items():
        result = session.get(url)
        if result.status != 200:
            logger.warning("%s: fund-characteristics page failed (status %d), skipping", ticker, result.status)
            continue
        parsed = _parse_janus_characteristics(result.text())
        rows.append({
            "ticker": ticker, "effective_duration_years": _to_years(parsed.get("Effective Duration")),
            "yield_pct": _to_pct(parsed.get("Yield to Worst")), "yield_label": "Yield to Worst",
        })
        logger.info("%s: duration=%s, yield=%s", ticker, parsed.get("Effective Duration"), parsed.get("Yield to Worst"))

    if not rows:
        raise RuntimeError("fund-characteristics scrape returned nothing for any ticker")
    return pd.DataFrame(rows)


def _archive_yfinance_raw(ticker: str, df: pd.DataFrame) -> None:
    YFINANCE_RAW_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    path = YFINANCE_RAW_DIR / f"{ticker}_{stamp}.csv"
    df.to_csv(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    logger.debug("archived raw yfinance pull for %s to %s (sha256:%s...)", ticker, path, digest)


def scrape_price_history(tickers: list[str] | None = None) -> pd.DataFrame:
    tickers = tickers or EXTRA_TICKERS
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
        raise RuntimeError("yfinance price scrape returned nothing for any extra ticker")
    return pd.concat(frames, ignore_index=True)


def run() -> pd.DataFrame:
    prices = scrape_price_history()
    write_parquet(prices, OUT_PATH, Provenance(
        source_urls=["https://finance.yahoo.com (via yfinance)"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.macro.scrape_returns.scrape_price_history",
        notes="TLT/SPY only — AGG/HYG/BKLN/LQD/SHV/JAAA reused from Section 1's etf_prices.parquet.",
    ))

    session = CachedSession()
    characteristics = scrape_fund_characteristics(session)
    write_parquet(characteristics, CHARACTERISTICS_OUT_PATH, Provenance(
        source_urls=list(_ISHARES_PAGES.values()) + list(_JANUS_PAGES.values()),
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.macro.scrape_returns.scrape_fund_characteristics",
        notes="Effective duration + yield from each fund's own overview page (server-rendered characteristics panel, "
              "not the JS-gated full-holdings widget); iShares reports Yield to Maturity, Janus Henderson reports Yield to Worst.",
    ))
    return prices


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
