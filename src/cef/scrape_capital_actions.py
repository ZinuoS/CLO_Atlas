"""Capital-formation events for listed CLO CEFs (Section 2 deep-dive) —
ATM common-stock issuance tape and preferred/term-preferred stock series,
from EDGAR 424B3/497 prospectus supplements.

Two distinct filing styles discovered by reading actual filings, not
assumed from the form type:
  - Oxford Lane (OXLC) files periodic "prior sales" updates that state, in
    one sentence, the exact shares sold and gross/net proceeds since the
    last supplement ("From <date> to <date>, we sold a total of <N> shares
    ... capital raised was approximately $X million and net proceeds were
    approximately $Y million") — a clean, regex-extractable ATM tape.
  - Eagle Point (ECC) files program-update supplements that restate the
    *authorized* offering size and enumerate outstanding preferred/term-
    preferred series (name, coupon, maturity) rather than periodic sales
    totals — good for the preferred-series capital-structure table, not
    the ATM tape.

Both patterns are applied to every fund's filings; each fund's real filing
style determines which table it actually populates. `shares outstanding` is
NOT available as clean structured XBRL for these filers (checked via
data.sec.gov/api/xbrl/companyfacts/ — the `cef` taxonomy category has only a
single "OutstandingSecurityHeldShares" fact, not a real history) — but
Oxford Lane's same 424B3 supplements also carry a "FINANCIAL UPDATE"
paragraph disclosing a preliminary NAV-per-share estimate range AND total
shares outstanding as of a specific recent month-end, at every filing that
includes one. `scrape_nav_disclosures` extracts both, giving a real,
dated NAV series that lines up almost exactly with the ATM tape's filing
dates — enough to compute a genuine historical premium/discount at each
disclosure, not just at the single current-day snapshot Section 2's
book-value proxy is limited to.
"""
from __future__ import annotations

import datetime as dt
import logging
import re

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.cef.scrape_capital_actions")

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik_nodash}/{accession_nodash}/{doc}"

OUT_ATM_TAPE = config.INTERIM_DIR / "cef_atm_tape.parquet"
OUT_PREFERRED_SERIES = config.INTERIM_DIR / "cef_preferred_series.parquet"
OUT_NAV_DISCLOSURES = config.INTERIM_DIR / "cef_nav_disclosures.parquet"

_NAV_ESTIMATE_PATTERN = re.compile(
    r"NAV[^.]{0,20}per share of our common stock as of\s+([A-Z][a-z]+ \d{1,2}, \d{4}),?\s+is between\s+"
    r"\$\s*(\d+\.\d+),?\s+and\s+\$\s*(\d+\.\d+)",
    re.IGNORECASE,
)
_SHARES_OUTSTANDING_PATTERN = re.compile(
    r"As of\s+([A-Z][a-z]+ \d{1,2}, \d{4}),?\s+the\s+Company\s+had\s+approximately\s+([\d,.]+)\s*(million)?\s+"
    r"shares\s+of\s+common\s+stock\s+issued\s+and\s+outstanding",
    re.IGNORECASE,
)

_ATM_SALES_PATTERN = re.compile(
    r"[Ff]rom\s+([A-Z][a-z]+ \d{1,2},? \d{4})\s+to\s+([A-Z][a-z]+ \d{1,2},? \d{4}),?\s+we\s+sold\s+a\s+total\s+of\s+"
    r"([\d,]+)\s+shares[\s\S]*?capital\s+raised[\s\S]*?\$([\d.,]+)\s*(million|billion)[\s\S]*?net\s+proceeds\s+were\s+approximately\s+"
    r"\$([\d.,]+)\s*(million|billion)",
)
_PREFERRED_SERIES_PATTERN = re.compile(
    r"([\d.]+)%\s+(Series\s+[A-Z0-9]+)\s+(Term\s+Preferred\s+(?:Stock|Shares)(?:\s+due\s+(\d{4}))?|Preferred\s+Stock)",
    re.IGNORECASE,
)


def _fetch_filing_list(session: CachedSession, cik: str, forms: tuple[str, ...], limit: int) -> list[dict]:
    result = session.get(SUBMISSIONS_URL.format(cik=cik))
    if result.status != 200:
        logger.warning("CIK %s: submissions lookup failed (status %d)", cik, result.status)
        return []
    recent = result.json()["filings"]["recent"]
    out = []
    for i, form in enumerate(recent["form"]):
        if form in forms:
            out.append({
                "accession": recent["accessionNumber"][i], "doc": recent["primaryDocument"][i],
                "date": recent["filingDate"][i], "form": form,
            })
    return out[:limit]


def _fetch_text(session: CachedSession, cik: str, accession: str, doc: str) -> str | None:
    from bs4 import BeautifulSoup
    url = DOC_URL.format(cik_nodash=cik.lstrip("0"), accession_nodash=accession.replace("-", ""), doc=doc)
    result = session.get(url)
    if result.status != 200:
        return None
    import warnings
    from bs4 import XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    soup = BeautifulSoup(result.text(), "lxml")
    return soup.get_text(" ", strip=True)


def scrape_atm_tape(session: CachedSession, tickers_ciks: dict[str, str], limit_per_fund: int = 60) -> pd.DataFrame:
    rows = []
    for ticker, cik in tickers_ciks.items():
        filings = _fetch_filing_list(session, cik, ("424B3", "497"), limit_per_fund)
        for filing in filings:
            text = _fetch_text(session, cik, filing["accession"], filing["doc"])
            if not text:
                continue
            match = _ATM_SALES_PATTERN.search(text)
            if not match:
                continue
            start, end, shares, gross, gross_unit, net, net_unit = match.groups()
            gross_millions = float(gross.replace(",", "")) * (1000 if gross_unit.lower() == "billion" else 1)
            net_millions = float(net.replace(",", "")) * (1000 if net_unit.lower() == "billion" else 1)
            rows.append({
                "ticker": ticker, "filing_date": filing["date"], "period_start": start, "period_end": end,
                "shares_sold": int(shares.replace(",", "")), "gross_proceeds_millions": gross_millions,
                "net_proceeds_millions": net_millions,
            })
        logger.info("%s: checked %d filings, found ATM-sales language in some subset", ticker, len(filings))
    return pd.DataFrame(rows)


def _normalize_series_name(series: str) -> str:
    """Filings render the same series inconsistently across documents
    ("SERIES C" / "Series C" / "Series\\nC" from wrapped source lines) —
    collapse whitespace and case before using this as a dedup key."""
    return re.sub(r"\s+", " ", series).strip().upper()


def scrape_preferred_series(session: CachedSession, tickers_ciks: dict[str, str], limit_per_fund: int = 60) -> pd.DataFrame:
    rows = []
    for ticker, cik in tickers_ciks.items():
        filings = _fetch_filing_list(session, cik, ("424B3", "497", "424B5"), limit_per_fund)
        best_by_key: dict[tuple, dict] = {}
        for filing in filings:
            text = _fetch_text(session, cik, filing["accession"], filing["doc"])
            if not text:
                continue
            for match in _PREFERRED_SERIES_PATTERN.finditer(text):
                coupon, series, kind, maturity = match.groups()
                series_norm = _normalize_series_name(series)
                key = (ticker, series_norm, round(float(coupon), 3))
                row = {
                    "ticker": ticker, "series": series_norm, "coupon_pct": float(coupon),
                    "is_term_preferred": "term" in kind.lower(), "maturity_year": int(maturity) if maturity else None,
                    "first_seen_filing_date": filing["date"],
                }
                # Filings are iterated newest-first (submissions API order),
                # so the last one processed for a key is the earliest sighting.
                best_by_key[key] = row
        rows.extend(best_by_key.values())
    return pd.DataFrame(rows)


def scrape_nav_disclosures(session: CachedSession, tickers_ciks: dict[str, str], limit_per_fund: int = 60) -> pd.DataFrame:
    """NAV-per-share estimate range + shares outstanding, both as-of a
    specific recent month-end, from each fund's "FINANCIAL UPDATE"
    paragraph where present (currently only found in Oxford Lane's
    filings). Rows come from whichever filings actually disclosed each
    piece — a filing may have NAV without shares or vice versa."""
    rows = []
    for ticker, cik in tickers_ciks.items():
        filings = _fetch_filing_list(session, cik, ("424B3", "497"), limit_per_fund)
        for filing in filings:
            text = _fetch_text(session, cik, filing["accession"], filing["doc"])
            if not text:
                continue
            nav_match = _NAV_ESTIMATE_PATTERN.search(text)
            shares_match = _SHARES_OUTSTANDING_PATTERN.search(text)
            if not nav_match and not shares_match:
                continue
            row = {"ticker": ticker, "filing_date": filing["date"]}
            if nav_match:
                as_of, nav_low, nav_high = nav_match.groups()
                row["nav_as_of"] = as_of
                row["nav_low"] = float(nav_low)
                row["nav_high"] = float(nav_high)
                row["nav_mid"] = (float(nav_low) + float(nav_high)) / 2
            if shares_match:
                as_of, shares, unit = shares_match.groups()
                row["shares_as_of"] = as_of
                shares_val = float(shares.replace(",", ""))
                row["shares_outstanding"] = shares_val * (1e6 if unit else 1)
            rows.append(row)
        logger.info("%s: %d/%d filings had a NAV/shares disclosure", ticker,
                     sum(1 for r in rows if r["ticker"] == ticker), len(filings))
    return pd.DataFrame(rows)


def run() -> dict[str, pd.DataFrame]:
    session = CachedSession()
    atm_tape = scrape_atm_tape(session, config.CLO_CEF_CIKS)
    write_parquet(atm_tape, OUT_ATM_TAPE, Provenance(
        source_urls=["https://data.sec.gov/submissions/", "https://www.sec.gov/Archives/edgar/"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.cef.scrape_capital_actions.scrape_atm_tape",
        notes="Extracted from 424B3/497 'prior sales' language; currently only Oxford Lane (OXLC) phrases its "
              "supplements this way among the funds checked.",
    ))

    preferred = scrape_preferred_series(session, config.CLO_CEF_CIKS)
    write_parquet(preferred, OUT_PREFERRED_SERIES, Provenance(
        source_urls=["https://data.sec.gov/submissions/", "https://www.sec.gov/Archives/edgar/"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.cef.scrape_capital_actions.scrape_preferred_series",
        notes="Deduped by (ticker, series, coupon); maturity_year is None for perpetual preferred (not term preferred).",
    ))

    nav_disclosures = scrape_nav_disclosures(session, config.CLO_CEF_CIKS)
    write_parquet(nav_disclosures, OUT_NAV_DISCLOSURES, Provenance(
        source_urls=["https://data.sec.gov/submissions/", "https://www.sec.gov/Archives/edgar/"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.cef.scrape_capital_actions.scrape_nav_disclosures",
        notes="From 'FINANCIAL UPDATE' paragraphs disclosing a preliminary NAV-per-share estimate range and/or shares "
              "outstanding as of a recent month-end; currently only found in Oxford Lane's (OXLC) filings.",
    ))

    logger.info("atm_tape=%d rows, preferred_series=%d rows, nav_disclosures=%d rows",
                len(atm_tape), len(preferred), len(nav_disclosures))
    return {"atm_tape": atm_tape, "preferred_series": preferred, "nav_disclosures": nav_disclosures}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
