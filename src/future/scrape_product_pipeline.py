"""EDGAR full-text search (efts.sec.gov, free, no key) for fund-registration
filings mentioning CLOs — the registered product pipeline (Part C): new CLO
ETFs, interval funds, tender-offer funds, by filing date and sponsor.

N-2 = closed-end fund/BDC registration (incl. non-traded/interval funds);
485APOS = open-end fund (ETF/mutual fund) registration amendment; N-1A =
open-end fund registration. Queried separately per form — the search API's
`forms` parameter 500'd when comma-joined across multiple types in testing
(2026-07-11), so this loops one form at a time instead.
"""
from __future__ import annotations

import datetime as dt
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.future.scrape_product_pipeline")

OUT_PATH = config.INTERIM_DIR / "future_product_pipeline.parquet"
API_URL = "https://efts.sec.gov/LATEST/search-index"

PIPELINE_FORMS = ["N-2", "485APOS", "N-1A"]
QUERY_TERM = '"collateralized loan obligation"'


def scrape_pipeline_filings(session: CachedSession, forms: list[str] | None = None, max_pages_per_form: int = 3) -> pd.DataFrame:
    forms = forms or PIPELINE_FORMS
    rows = []
    for form in forms:
        for page in range(max_pages_per_form):
            result = session.get(API_URL, params={"q": QUERY_TERM, "forms": form, "from": page * 10})
            if result.status != 200:
                logger.warning("EDGAR full-text search for form %s page %d failed (status %d)", form, page, result.status)
                break
            payload = result.json()
            hits = payload.get("hits", {}).get("hits", [])
            if not hits:
                break
            for hit in hits:
                src = hit["_source"]
                rows.append({
                    "form": src.get("form"), "filer": ", ".join(src.get("display_names", [])),
                    "cik": ", ".join(src.get("ciks", [])), "file_date": src.get("file_date"),
                    "file_description": src.get("file_description"), "accession": src.get("adsh"),
                })
        logger.info("EDGAR full-text search, form %s: %d filings", form, sum(1 for r in rows if r["form"] == form or (r["form"] or "").startswith(form)))
    return pd.DataFrame(rows).drop_duplicates(subset=["accession", "filer"])


def run() -> pd.DataFrame:
    session = CachedSession()
    df = scrape_pipeline_filings(session)
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[API_URL], scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.future.scrape_product_pipeline",
        notes="EDGAR full-text search covers filings since 2001; up to 30 filings per form type (3 pages x 10), not exhaustive.",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
