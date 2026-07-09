"""CLO-equity portfolio disclosures for listed CEFs (Section 2), from EDGAR
NPORT-P filings.

The mission brief suggested parsing N-CSR/N-CSRS HTML/PDF portfolio tables
with a per-fund parser. This uses NPORT-P instead: a standardized,
machine-readable XML that every registered fund (these CEFs included) files
monthly/quarterly, covering the same portfolio detail (position, cost/fair
value, coupon, maturity) without per-fund table-layout guesswork. Verified
2026-07-09 against ECC's (CIK 1604174) filings.

Fetch/parse logic lives in src/common/nport.py, shared with Section 3's
bank-loan-fund scraper (src/edgar/scrape_nport.py) — same filing format,
different fund universe.
"""
from __future__ import annotations

import datetime as dt
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession
from src.common.nport import parse_nport_xml, scrape_fund, scrape_funds  # noqa: F401 (re-exported for tests)

logger = logging.getLogger("clo_atlas.cef.scrape_filings")

OUT_PATH = config.INTERIM_DIR / "cef_clo_positions.parquet"


def run(limit_per_fund: int = 4) -> pd.DataFrame:
    session = CachedSession()
    combined = scrape_funds(session, config.CLO_CEF_CIKS, limit_per_fund=limit_per_fund)

    if combined.empty:
        logger.warning("no CEF filing data scraped this run")
        if OUT_PATH.exists():
            return pd.read_parquet(OUT_PATH)
        return pd.DataFrame()

    write_parquet(combined, OUT_PATH, Provenance(
        source_urls=["https://data.sec.gov/submissions/", "https://www.sec.gov/Archives/edgar/"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.cef.scrape_filings",
        notes=f"NPORT-P portfolio positions, up to {limit_per_fund} most recent filings per fund.",
    ))
    logger.info("wrote %d total positions (%d CLO-tagged) to %s",
                len(combined), combined["is_clo"].sum(), OUT_PATH)
    return combined


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
