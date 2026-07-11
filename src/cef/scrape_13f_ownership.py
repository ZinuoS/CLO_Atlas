"""Institutional ownership proxy for listed CLO CEFs (Section 2 deep-dive),
from EDGAR Schedule 13G/13G-A filings (>5% beneficial owners), not a full
13F aggregation across every institutional filer.

13G only captures holders crossing the 5% threshold, so summed 13G
ownership is a LOWER BOUND on institutional ownership, not the complete
institutional share — smaller institutional positions (each individually
<5%) are invisible to this method. Labeled as a floor throughout, not
asserted as total institutional ownership.
"""
from __future__ import annotations

import datetime as dt
import logging
import re

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.cef.scrape_13f_ownership")

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik_nodash}/{accession_nodash}/{doc}"

OUT_PATH = config.INTERIM_DIR / "cef_13g_ownership.parquet"

_FILER_PATTERN = re.compile(r"NAME OF REPORTING PERSON[S]?\s*I\.?R\.?S\.?[^A-Za-z]*?([A-Z][A-Za-z0-9.,&' \-]{2,60})", re.IGNORECASE)
_PERCENT_PATTERN = re.compile(r"Percent of Class:?\s*([\d.]+)", re.IGNORECASE)
_AMOUNT_PATTERN = re.compile(r"Amount beneficially owned:?\s*([\d,]+)", re.IGNORECASE)


def _fetch_13g_filings(session: CachedSession, cik: str, limit: int) -> list[dict]:
    result = session.get(SUBMISSIONS_URL.format(cik=cik))
    if result.status != 200:
        return []
    recent = result.json()["filings"]["recent"]
    out = [{"accession": recent["accessionNumber"][i], "doc": recent["primaryDocument"][i], "date": recent["filingDate"][i]}
           for i, f in enumerate(recent["form"]) if f in ("SC 13G", "SC 13G/A")]
    return out[:limit]


def scrape_ownership(session: CachedSession, tickers_ciks: dict[str, str], limit_per_fund: int = 40) -> pd.DataFrame:
    from bs4 import BeautifulSoup
    import warnings
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

    rows = []
    for ticker, cik in tickers_ciks.items():
        filings = _fetch_13g_filings(session, cik, limit_per_fund)
        for filing in filings:
            url = DOC_URL.format(cik_nodash=cik.lstrip("0"), accession_nodash=filing["accession"].replace("-", ""), doc=filing["doc"])
            result = session.get(url)
            if result.status != 200:
                continue
            text = BeautifulSoup(result.text(), "lxml").get_text(" ", strip=True)
            filer_match = _FILER_PATTERN.search(text)
            pct_match = _PERCENT_PATTERN.search(text)
            amount_match = _AMOUNT_PATTERN.search(text)
            if not pct_match:
                continue
            rows.append({
                "ticker": ticker, "filing_date": filing["date"],
                "filer": filer_match.group(1).strip() if filer_match else None,
                "percent_of_class": float(pct_match.group(1)),
                "shares_owned": int(amount_match.group(1).replace(",", "")) if amount_match else None,
            })
        logger.info("%s: %d/%d 13G filings had a parseable percent-of-class", ticker,
                     sum(1 for r in rows if r["ticker"] == ticker), len(filings))
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    session = CachedSession()
    df = scrape_ownership(session, config.CLO_CEF_CIKS)
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=["https://data.sec.gov/submissions/", "https://www.sec.gov/Archives/edgar/"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.cef.scrape_13f_ownership",
        notes="Schedule 13G/13G-A (>5% holders) only — a lower bound on institutional ownership, not the complete share.",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
