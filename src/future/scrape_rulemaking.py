"""Federal Register API (free, no key) — rules and proposed rules whose
text mentions CLOs (Part C: legal/regulatory regime) and Section 6 v2's
regulator corpus alike. Comment counts (via regulations.gov, where linked)
would be a controversy proxy; regulations.gov needs an API key not present
in this environment, so only Federal Register's own metadata (agency,
document type, publication date, abstract) is used here.
"""
from __future__ import annotations

import datetime as dt
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.future.scrape_rulemaking")

OUT_PATH = config.INTERIM_DIR / "future_federal_register.parquet"
API_URL = "https://www.federalregister.gov/api/v1/articles.json"


def scrape_federal_register(session: CachedSession, term: str = "collateralized loan obligation", max_pages: int = 10) -> pd.DataFrame:
    rows = []
    for page in range(1, max_pages + 1):
        params = {"conditions[term]": term, "per_page": 50, "page": page,
                  "fields[]": ["title", "type", "abstract", "document_number", "publication_date", "agencies", "html_url"]}
        result = session.get(API_URL, params=params)
        if result.status != 200:
            logger.warning("Federal Register page %d failed (status %d)", page, result.status)
            break
        payload = result.json()
        results = payload.get("results", [])
        if not results:
            break
        for r in results:
            agencies = ", ".join(a.get("name", "") for a in r.get("agencies", []))
            rows.append({
                "title": r.get("title"), "type": r.get("type"), "abstract": r.get("abstract"),
                "document_number": r.get("document_number"), "publication_date": r.get("publication_date"),
                "agencies": agencies, "url": r.get("html_url"),
            })
        if not payload.get("next_page_url"):
            break
    logger.info("Federal Register %r: %d documents across %d page(s)", term, len(rows), page)
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    session = CachedSession()
    df = scrape_federal_register(session)
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[API_URL], scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.future.scrape_rulemaking",
        notes="Federal Register metadata only (no full document text); regulations.gov comment counts need an API key not present here.",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
