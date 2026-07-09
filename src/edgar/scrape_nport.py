"""N-PORT-P filings for large bank-loan closed-end funds (Section 3):
loan and CLO positions, extending the same disclosure Section 2 uses for
CLO-focused CEFs to funds whose primary strategy is broadly syndicated
loans, not CLOs specifically — a different cross-section of who holds
CLO/loan risk.

Fetch/parse logic lives in src/common/nport.py, shared with Section 2.
"""
from __future__ import annotations

import datetime as dt
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession
from src.common.nport import scrape_funds

logger = logging.getLogger("clo_atlas.edgar.scrape_nport")

OUT_PATH = config.INTERIM_DIR / "bank_loan_fund_positions.parquet"


def run(limit_per_fund: int = 4) -> pd.DataFrame:
    session = CachedSession()
    combined = scrape_funds(session, config.BANK_LOAN_FUND_CIKS, limit_per_fund=limit_per_fund)

    if combined.empty:
        logger.warning("no bank-loan fund filing data scraped this run")
        if OUT_PATH.exists():
            return pd.read_parquet(OUT_PATH)
        return pd.DataFrame()

    write_parquet(combined, OUT_PATH, Provenance(
        source_urls=["https://data.sec.gov/submissions/", "https://www.sec.gov/Archives/edgar/"],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.edgar.scrape_nport",
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
