"""Regulator financial-stability report archives (Section 6): Fed Financial
Stability Reports and BIS Quarterly Reviews, both free PDFs, no login.

IMF GFSR and ECB FSR were investigated but not resolved this pass — see
docs/excluded_sources.md (IMF's page redirects to a structure this project
couldn't map to a stable PDF pattern in the time available; ECB's index page
only exposes its current issue's URL client-side, with the historical
archive requiring more discovery than was in budget). Logged as a gap, not
faked. Congressional testimony (govinfo.gov) and Fed speeches are a
documented enhancement path, not implemented this pass either.
"""
from __future__ import annotations

import datetime as dt
import logging
import re

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession
from src.common.text import pdf_to_text

logger = logging.getLogger("clo_atlas.sentiment.scrape_regulators")

OUT_PATH = config.INTERIM_DIR / "regulator_reports.parquet"

FED_FSR_LISTING_URL = "https://www.federalreserve.gov/publications/financial-stability-report.htm"
FED_FSR_PDF_PATTERN = re.compile(r'href="(/publications/files/financial-stability-report-(\d{8})\.pdf)"')
BIS_QTR_URL = "https://www.bis.org/publ/qtrpdf/r_qt{yymm}.pdf"


def _pdf_bytes_to_tempfile_text(pdf_bytes: bytes) -> str:
    import io
    return pdf_to_text(io.BytesIO(pdf_bytes))


def discover_fed_fsr_urls(session: CachedSession) -> list[dict]:
    result = session.get(FED_FSR_LISTING_URL)
    if result.status != 200:
        logger.warning("Fed FSR listing page failed (status %d)", result.status)
        return []
    matches = FED_FSR_PDF_PATTERN.findall(result.text())
    seen = set()
    out = []
    for path, date_str in matches:
        if path in seen:
            continue
        seen.add(path)
        out.append({"url": f"https://www.federalreserve.gov{path}",
                    "date": dt.datetime.strptime(date_str, "%Y%m%d").date().isoformat()})
    return out


def discover_bis_qtr_urls() -> list[dict]:
    urls = []
    this_year = dt.date.today().year
    for year in range(config.REGULATOR_REPORT_START_YEAR, this_year + 1):
        yy = str(year)[2:]
        for mm in config.BIS_QTR_MONTHS:
            urls.append({"url": BIS_QTR_URL.format(yymm=f"{yy}{mm}"), "date": f"{year}-{mm}-28"})
    return urls


def scrape_fed_fsr(session: CachedSession) -> pd.DataFrame:
    rows = []
    for item in discover_fed_fsr_urls(session):
        try:
            result = session.get(item["url"])
            if result.status != 200:
                logger.warning("Fed FSR %s failed (status %d)", item["date"], result.status)
                continue
            text = _pdf_bytes_to_tempfile_text(result.content)
        except Exception as exc:
            logger.warning("Fed FSR %s failed to parse (%s)", item["date"], exc)
            continue
        rows.append({"institution": "Federal Reserve", "report": "Financial Stability Report",
                     "date": item["date"], "url": item["url"], "text": text})
        logger.info("Fed FSR %s: %d chars", item["date"], len(text))
    return pd.DataFrame(rows)


def scrape_bis_qtr(session: CachedSession) -> pd.DataFrame:
    rows = []
    for item in discover_bis_qtr_urls():
        try:
            result = session.get(item["url"])
        except Exception as exc:
            logger.warning("BIS QR %s failed (%s)", item["date"], exc)
            continue
        if result.status != 200:
            continue  # many quarter/year combos in the generated grid don't exist; not every miss is worth a warning
        try:
            text = _pdf_bytes_to_tempfile_text(result.content)
        except Exception as exc:
            logger.warning("BIS QR %s failed to parse (%s)", item["date"], exc)
            continue
        rows.append({"institution": "BIS", "report": "Quarterly Review",
                     "date": item["date"], "url": item["url"], "text": text})
        logger.info("BIS QR %s: %d chars", item["date"], len(text))
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    session = CachedSession()
    fed = scrape_fed_fsr(session)
    bis = scrape_bis_qtr(session)
    combined = pd.concat([fed, bis], ignore_index=True)

    if combined.empty:
        logger.warning("no regulator reports scraped this run")
        if OUT_PATH.exists():
            return pd.read_parquet(OUT_PATH)
        return pd.DataFrame()

    write_parquet(combined, OUT_PATH, Provenance(
        source_urls=[FED_FSR_LISTING_URL, "https://www.bis.org/publ/qtrpdf/"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.sentiment.scrape_regulators",
        notes="IMF GFSR and ECB FSR not resolved this pass — see docs/excluded_sources.md.",
    ))
    logger.info("wrote %d regulator reports to %s", len(combined), OUT_PATH)
    return combined


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
