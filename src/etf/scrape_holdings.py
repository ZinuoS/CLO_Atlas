"""Daily full-holdings scraper for CLO ETFs (Section 1).

For funds with a confirmed, non-JS-gated holdings page (currently Janus
Henderson's JAAA/JBBB — see config.CLO_ETF_TICKERS), fetches the server-
rendered "full holdings" HTML table directly: no login, no captcha, no
JS execution required, just CachedSession + BeautifulSoup. Verified by hand
on 2026-07-08: robots.txt on janushenderson.com allows it, and the page
embeds all ~600 tranche-level rows server-side.

For funds where a plain-HTTP path could not be found (VanEck CLOB/CLOI sit
behind a cookie-consent redirect loop, iShares CLOA/CLOD's full-holdings data
loads via a client-rendered widget with no discovered JSON endpoint, Invesco
ICLO 406s a scripted client, Eldridge/Panagram CLOZ only publishes quarterly
PDFs) this scraper does NOT attempt headless-browser automation to defeat
those walls — that's out of scope for "polite scraping" here. It logs the gap
and continues; see docs/excluded_sources.md. NAV/price/flow analysis for
those tickers still runs from scrape_nav_flows.py (yfinance), which doesn't
need the issuer site at all.

Output: data/interim/etf_holdings.parquet, tidy panel with one row per
CUSIP per fund per scrape date:
  date, fund, cusip, tranche_ticker, deal_name_raw, manager_raw, par,
  market_value, price, weight
"""
from __future__ import annotations

import datetime as dt
import logging
import re

import pandas as pd
from bs4 import BeautifulSoup

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.etf.scrape_holdings")

OUT_PATH = config.INTERIM_DIR / "etf_holdings.parquet"

_AS_OF_PATTERN = re.compile(r"As of\s*([\d/]+)", re.IGNORECASE)
_MANAGER_PREFIX_PATTERN = re.compile(r"^([A-Za-z]+)")
_MONEY_PATTERN = re.compile(r"[^0-9.\-]")


def _to_float(raw: str) -> float | None:
    if not raw or raw.strip() in ("-", ""):
        return None
    cleaned = _MONEY_PATTERN.sub("", raw)
    try:
        return float(cleaned) if cleaned not in ("", "-", ".") else None
    except ValueError:
        return None


def parse_janus_henderson_table(html: str, fund: str) -> pd.DataFrame:
    """Parse the server-rendered '#full holdings' table shared by JAAA/JBBB.

    Columns as of 2026-07-08: [description, Ticker, Cusip, Underlying Security,
    Strike Price, Quantity, Notional Value, Market Value, Weight %, Current
    Market Value]. The first cell is a long free-text description (security
    name + tranche + coupon + maturity); we keep it raw as `deal_name_raw` and
    derive a rough `manager_raw` from the Ticker column's alpha prefix — exact
    manager names get canonicalized downstream by common/entity.py, not here.
    """
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table")
    if not tables:
        raise ValueError(f"no holdings table found for {fund}")
    table = tables[0]
    rows = table.find_all("tr")
    if not rows:
        raise ValueError(f"holdings table for {fund} has no rows")

    header_text = rows[0].find_all(["th", "td"])[0].get_text(strip=True) if rows[0].find_all(["th", "td"]) else ""
    as_of_match = _AS_OF_PATTERN.search(header_text)
    as_of_date = None
    if as_of_match:
        try:
            as_of_date = dt.datetime.strptime(as_of_match.group(1), "%m/%d/%Y").date()
        except ValueError:
            try:
                as_of_date = dt.datetime.strptime(as_of_match.group(1), "%d/%m/%Y").date()
            except ValueError:
                as_of_date = None
    as_of_date = as_of_date or dt.date.today()

    records = []
    skipped = 0
    for row in rows[1:]:
        cells = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
        if len(cells) < 9:
            skipped += 1
            continue
        deal_name_raw, ticker, cusip = cells[0], cells[1], cells[2]
        quantity, market_value, weight = cells[5], cells[7], cells[8]
        if not ticker and not cusip:
            skipped += 1
            continue
        manager_match = _MANAGER_PREFIX_PATTERN.match(ticker or "")
        manager_raw = manager_match.group(1) if manager_match else None
        par = _to_float(quantity)
        mv = _to_float(market_value)
        wt = _to_float(weight)
        price = (mv / par * 100) if (par and mv) else None
        records.append({
            "date": as_of_date, "fund": fund, "cusip": cusip or None,
            "tranche_ticker": ticker or None, "deal_name_raw": deal_name_raw or None,
            "manager_raw": manager_raw, "par": par, "market_value": mv,
            "price": price, "weight": wt,
        })

    if skipped:
        logger.warning("%s: skipped %d malformed holdings rows out of %d", fund, skipped, len(rows) - 1)
    if not records:
        raise ValueError(f"parsed zero usable holdings rows for {fund}")
    return pd.DataFrame.from_records(records)


_PARSERS = {
    "janus_henderson_table": parse_janus_henderson_table,
}


def scrape_fund_holdings(session: CachedSession, fund: str, meta: dict) -> pd.DataFrame | None:
    url = meta.get("holdings_url")
    parser_name = meta.get("holdings_parser")
    if not url or not parser_name:
        logger.warning("%s: no scrapable holdings endpoint on file, skipping (see docs/excluded_sources.md)", fund)
        return None

    try:
        result = session.get(url)
    except Exception as exc:
        logger.warning("%s: fetch failed (%s), skipping this run", fund, exc)
        return None

    if result.status != 200:
        logger.warning("%s: holdings page returned status %d, skipping this run", fund, result.status)
        return None

    parser = _PARSERS[parser_name]
    try:
        df = parser(result.text(), fund)
    except Exception as exc:
        logger.warning("%s: parse failed (%s), skipping this run", fund, exc)
        return None

    logger.info("%s: parsed %d holdings rows as of %s", fund, len(df), df["date"].iloc[0])
    return df


def run(force_refetch: bool = False) -> pd.DataFrame:
    session = CachedSession(force_refetch=force_refetch)
    frames = []
    source_urls = []
    for fund, meta in config.CLO_ETF_TICKERS.items():
        df = scrape_fund_holdings(session, fund, meta)
        if df is not None:
            frames.append(df)
            source_urls.append(meta["holdings_url"])

    if not frames:
        logger.warning("no fund holdings scraped this run; leaving existing cache (if any) untouched")
        if OUT_PATH.exists():
            return pd.read_parquet(OUT_PATH)
        return pd.DataFrame(columns=["date", "fund", "cusip", "tranche_ticker", "deal_name_raw",
                                       "manager_raw", "par", "market_value", "price", "weight"])

    new_data = pd.concat(frames, ignore_index=True)
    # A fund's table can legitimately list the same CUSIP+tranche twice (e.g.
    # split lots); aggregate rather than arbitrarily dropping one, so par/
    # market_value stay accurate.
    new_data = (
        new_data.groupby(["date", "fund", "cusip", "tranche_ticker"], as_index=False, dropna=False)
        .agg({"deal_name_raw": "first", "manager_raw": "first", "par": "sum",
              "market_value": "sum", "price": "mean", "weight": "sum"})
    )

    if OUT_PATH.exists():
        existing = pd.read_parquet(OUT_PATH)
        combined = pd.concat([existing, new_data], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date", "fund", "cusip", "tranche_ticker"], keep="last")
    else:
        combined = new_data

    write_parquet(combined, OUT_PATH, Provenance(
        source_urls=sorted(set(source_urls)),
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.etf.scrape_holdings",
        notes=f"funds with a resolved parser this run: {sorted(set(new_data['fund']))}",
    ))
    logger.info("wrote %d total holdings rows (%d new) to %s", len(combined), len(new_data), OUT_PATH)
    return combined


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
