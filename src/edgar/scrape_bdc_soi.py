"""BDC Schedules of Investment from 10-K/10-Q filings (Section 3) — the
loan-level layer.

The mission brief anticipated parsing the giant combined 10-K/10-Q HTML
document with a header-detection table parser. In practice that document
(20+ MB, hundreds of unrelated tables) doesn't cleanly yield the SOI at all
via pandas.read_html — the position-level detail isn't in a normal <table>
grid there. What works: every EDGAR filing with inline XBRL also publishes
one clean, single-purpose "rendered report" HTML fragment per financial
statement (R1.htm, R2.htm, ...); FilingSummary.xml maps report numbers to
titles, and "CONSOLIDATED SCHEDULE OF INVESTMENTS" is reliably one of them.
That fragment is a single ~12,000-row table, but in XBRL-rendered long
format, not one-row-per-position: each position appears as an
"Investment, Identifier [Axis]: <company>, <instrument>" header row followed
by its Fair Value / Amortized Cost / Principal / Coupon / Spread / Shares
sub-rows. This module reshapes that into tidy one-row-per-position-per-period
records. Verified 2026-07-09 against ARCC (CIK 1287750).

Resilience: a malformed or unexpectedly-shaped filing raises inside
`parse_soi_report`, which `scrape_bdc` catches and logs per the mission
brief's "accept per-filing failures logged, not fatal."
"""
from __future__ import annotations

import datetime as dt
import logging
import re

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.edgar.scrape_bdc_soi")

OUT_PATH = config.INTERIM_DIR / "bdc_soi_positions.parquet"

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:0>10}.json"
FILING_SUMMARY_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/FilingSummary.xml"
REPORT_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{report_file}"

_IDENTIFIER_PREFIX = "Investment, Identifier [Axis]: "
_METRIC_ROW_LABELS = {"Amortized Cost", "Fair Value", "Principal", "Coupon", "Spread",
                       "Shares/Units", "Coupon, PIK", "Shares (as a percent)"}
_DATE_PATTERN = re.compile(r"[A-Z][a-z]{2}\.\s\d{1,2},\s\d{4}")
_INSTRUMENT_PATTERN = re.compile(
    r",\s*((?:First|Second|Third)\s+lien[^,]*|Senior\s+subordinated[^,]*|Unsecured[^,]*|"
    r"Preferred\s+stock[^,]*|Common\s+stock[^,]*|Warrant[^,]*|Membership\s+interest[^,]*|"
    r"Class\s+[A-Z][^,]*|Structured\s+[^,]*)$", re.IGNORECASE)


def find_soi_report(session: CachedSession, cik: str, accession_nodash: str) -> str | None:
    result = session.get(FILING_SUMMARY_URL.format(cik=cik, accession_nodash=accession_nodash))
    if result.status != 200:
        return None
    text = result.text()
    # Each <Report> block has a <LongName> and a <HtmlFileName>; find the one
    # whose LongName mentions the SOI and isn't the "(Parenthetical)" variant.
    for block in re.findall(r"<Report[^>]*>.*?</Report>", text, re.DOTALL):
        long_name_m = re.search(r"<LongName>(.*?)</LongName>", block)
        file_m = re.search(r"<HtmlFileName>(.*?)</HtmlFileName>", block)
        if not long_name_m or not file_m:
            continue
        name = long_name_m.group(1)
        if "SCHEDULE OF INVESTMENTS" in name.upper() and "PARENTHETICAL" not in name.upper():
            return file_m.group(1)
    return None


def parse_soi_report(html_text: str, fund: str) -> pd.DataFrame:
    tables = pd.read_html(pd.io.common.StringIO(html_text))
    soi = max(tables, key=lambda t: t.shape[0])
    if soi.shape[0] < 100 or soi.shape[1] < 5:
        raise ValueError(f"largest table ({soi.shape}) doesn't look like an SOI for {fund}")

    cols = list(soi.columns)
    period_cols = {cols[2]: "current", cols[4]: "prior"} if len(cols) >= 5 else {}
    if not period_cols:
        raise ValueError(f"unexpected SOI column layout for {fund}: {cols}")
    # Column headers for the same reporting date vary by fact type — some
    # carry extra unit text ("Mar. 31, 2026 USD ($) shares") depending on
    # which sub-block of the table pandas merged the header from. Extract
    # just the date so the same period always groups together regardless of
    # which column happened to report it.
    def _clean_period_label(label: str) -> str:
        m = _DATE_PATTERN.search(str(label))
        return m.group(0) if m else re.sub(r"\.\d+$", "", str(label))

    period_dates = {label: _clean_period_label(label) for label in period_cols}

    records: dict[tuple[str, str], dict] = {}
    current_id = None
    for _, row in soi.iterrows():
        label = str(row.iloc[0]).strip()
        if label.startswith(_IDENTIFIER_PREFIX):
            current_id = label[len(_IDENTIFIER_PREFIX):].strip()
            continue
        if current_id is None or label not in _METRIC_ROW_LABELS:
            continue
        for col_label, period_key in period_cols.items():
            key = (current_id, period_dates[col_label])
            records.setdefault(key, {"fund": fund, "investment_identifier": current_id,
                                       "period": period_dates[col_label]})
            records[key][label] = row[col_label]

    if not records:
        raise ValueError(f"parsed zero SOI positions for {fund}")

    df = pd.DataFrame(list(records.values()))
    df = df.rename(columns={"Amortized Cost": "amortized_cost", "Fair Value": "fair_value",
                             "Principal": "principal", "Coupon": "coupon", "Spread": "spread",
                             "Shares/Units": "shares_units", "Coupon, PIK": "coupon_pik"})

    def _to_num(s):
        return pd.to_numeric(s.astype(str).str.replace(r"[$,%]", "", regex=True).str.strip(), errors="coerce")

    for col in ("amortized_cost", "fair_value", "principal", "shares_units"):
        if col in df.columns:
            df[col] = _to_num(df[col])
    for col in ("coupon", "spread", "coupon_pik"):
        if col in df.columns:
            df[col] = _to_num(df[col])

    # Different filers tag identifiers differently: ARCC-style is free-text
    # comma-separated ("Company, First lien senior secured loan"); GBDC/OBDC/
    # MAIN-style is pipe-delimited ("Company | One stop 1 | Non-Affiliated
    # Issuer"). Try the pipe split first (unambiguous where present) and only
    # fall back to the comma/instrument-keyword regex when there's no pipe —
    # otherwise the pipe-style filers' "company" field ends up contaminated
    # with instrument/affiliation suffix text and never matches anyone else's
    # bare company name (this is exactly what broke cross-filer matching the
    # first time this ran).
    has_pipe = df["investment_identifier"].str.contains(r"\s\|\s")
    pipe_parts = df["investment_identifier"].str.split(r"\s\|\s", n=1, regex=True)
    df["company"] = df["investment_identifier"]
    df["instrument_type"] = pd.NA
    df.loc[has_pipe, "company"] = pipe_parts[has_pipe].str[0]
    df.loc[has_pipe, "instrument_type"] = pipe_parts[has_pipe].str[1]

    comma_instrument = df.loc[~has_pipe, "investment_identifier"].str.extract(_INSTRUMENT_PATTERN)[0]
    comma_has_match = comma_instrument.notna()
    comma_idx = comma_has_match[comma_has_match].index
    df.loc[comma_idx, "instrument_type"] = comma_instrument.loc[comma_idx]
    df.loc[comma_idx, "company"] = df.loc[comma_idx].apply(
        lambda r: r["investment_identifier"][: -(len(r["instrument_type"]) + 2)], axis=1)
    return df


def list_recent_filings(session: CachedSession, cik: str, forms=("10-K", "10-Q"), limit: int = 2) -> list[dict]:
    result = session.get(SUBMISSIONS_URL.format(cik=cik))
    if result.status != 200:
        logger.warning("CIK %s: submissions lookup failed (status %d)", cik, result.status)
        return []
    recent = result.json().get("filings", {}).get("recent", {})
    filings = [{"form": f, "accession": a, "filed": d}
               for f, a, d in zip(recent.get("form", []), recent.get("accessionNumber", []), recent.get("filingDate", []))
               if f in forms]
    return filings[:limit]


def scrape_bdc(session: CachedSession, fund: str, cik: str, limit: int = 2) -> pd.DataFrame | None:
    cik_int = str(int(cik))
    filings = list_recent_filings(session, cik, limit=limit)
    if not filings:
        logger.warning("%s: no 10-K/10-Q filings found", fund)
        return None

    frames = []
    for filing in filings:
        accession_nodash = filing["accession"].replace("-", "")
        try:
            report_file = find_soi_report(session, cik_int, accession_nodash)
            if not report_file:
                logger.warning("%s: no SOI report found in filing %s (FilingSummary.xml has no matching entry)",
                                fund, filing["accession"])
                continue
            result = session.get(REPORT_URL.format(cik=cik_int, accession_nodash=accession_nodash, report_file=report_file))
            if result.status != 200:
                logger.warning("%s: SOI report fetch failed for %s (status %d)", fund, filing["accession"], result.status)
                continue
            df = parse_soi_report(result.text(), fund)
        except Exception as exc:
            logger.warning("%s: SOI parse failed for filing %s (%s) — skipping this filing, not fatal",
                            fund, filing["accession"], exc)
            continue
        frames.append(df)
        logger.info("%s: parsed %d position-period rows from filing %s", fund, len(df), filing["accession"])

    if not frames:
        return None
    return pd.concat(frames, ignore_index=True)


def run(limit_per_fund: int = 2) -> pd.DataFrame:
    session = CachedSession()
    frames = []
    for fund, cik in config.BDC_CIKS.items():
        df = scrape_bdc(session, fund, cik, limit=limit_per_fund)
        if df is not None:
            frames.append(df)

    if not frames:
        logger.warning("no BDC SOI data scraped this run")
        if OUT_PATH.exists():
            return pd.read_parquet(OUT_PATH)
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["fund", "period", "investment_identifier"], keep="last")

    write_parquet(combined, OUT_PATH, Provenance(
        source_urls=["https://data.sec.gov/submissions/", "https://www.sec.gov/Archives/edgar/"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.edgar.scrape_bdc_soi",
        notes=f"SOI positions from EDGAR's rendered-XBRL report fragments, up to {limit_per_fund} filings per fund.",
    ))
    logger.info("wrote %d total position-period rows to %s", len(combined), OUT_PATH)
    return combined


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
