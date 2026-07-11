"""Regulator corpus expansion (Section 6 v2): Bank of England Financial
Stability Reports — the BoE has run some of the most explicit CLO/private-
credit stress analysis of any central bank (verified 2026-07-11: its Nov
2024 FSR landing page already discusses CLO/PE-securitization risk in its
own body text, not buried in a PDF appendix).

FSOC/OFR annual reports, congressional testimony (govinfo.gov), and Fed/BoE
speech archives are documented next steps, not implemented this pass —
logged in docs/excluded_sources.md rather than guessed at with unverified
URL patterns.
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

logger = logging.getLogger("clo_atlas.sentiment.scrape_regulators_v2")

OUT_PATH = config.INTERIM_DIR / "regulator_reports_v2.parquet"

BOE_LANDING_URL = "https://www.bankofengland.co.uk/financial-stability-report/{year}/{slug}-{year}"
_PDF_LINK_PATTERN = re.compile(r'href="(/-/media/boe/files/financial-stability-report/\d{4}/[^"]+\.pdf)"')
_BOE_CANDIDATE_MONTHS = ["june", "july", "november", "december"]


def discover_boe_fsr_urls(session: CachedSession, start_year: int = 2013) -> list[dict]:
    this_year = dt.date.today().year
    out = []
    for year in range(start_year, this_year + 1):
        for month in _BOE_CANDIDATE_MONTHS:
            landing = BOE_LANDING_URL.format(year=year, slug=month)
            result = session.get(landing)
            if result.status != 200:
                continue  # most year/month combos in this generated grid don't exist; not every miss is worth a warning
            match = _PDF_LINK_PATTERN.search(result.text())
            if not match:
                continue
            out.append({"url": f"https://www.bankofengland.co.uk{match.group(1)}", "date": f"{year}-{_month_num(month)}-28",
                        "landing_url": landing})
    return out


def _month_num(name: str) -> str:
    return {"june": "06", "july": "07", "november": "11", "december": "12"}[name]


def scrape_boe_fsr(session: CachedSession) -> pd.DataFrame:
    rows = []
    for item in discover_boe_fsr_urls(session):
        try:
            result = session.get(item["url"])
            if result.status != 200:
                logger.warning("BoE FSR %s failed (status %d)", item["date"], result.status)
                continue
            import io
            text = pdf_to_text(io.BytesIO(result.content))
        except Exception as exc:
            logger.warning("BoE FSR %s failed to parse (%s)", item["date"], exc)
            continue
        rows.append({"institution": "Bank of England", "report": "Financial Stability Report",
                     "date": item["date"], "url": item["url"], "text": text})
        logger.info("BoE FSR %s: %d chars", item["date"], len(text))
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    session = CachedSession()
    boe = scrape_boe_fsr(session)
    if boe.empty:
        logger.warning("no BoE FSR scraped this run")
        if OUT_PATH.exists():
            return pd.read_parquet(OUT_PATH)
        return pd.DataFrame()

    write_parquet(boe, OUT_PATH, Provenance(
        source_urls=[BOE_LANDING_URL],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.sentiment.scrape_regulators_v2",
        notes="Bank of England Financial Stability Reports; FSOC/OFR/congressional-testimony/speech archives are a "
              "documented next step, not implemented this pass.",
    ))
    logger.info("wrote %d BoE FSR reports to %s", len(boe), OUT_PATH)
    return boe


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
