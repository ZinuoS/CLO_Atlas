"""CourtListener/RECAP API (free, no key) — dockets matching leveraged-
finance creditor-conflict terms (Part C: the legal regime for the LME era).

Landmark case names weren't independently discovered from the news/ratings
corpora this pass (that cross-referencing is a documented next step); the
query terms below are the well-known public terms for this litigation wave
(uptier, drop-down/dropdown, priming, liability management exercise).
"""
from __future__ import annotations

import datetime as dt
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.future.scrape_litigation")

OUT_PATH = config.INTERIM_DIR / "future_litigation.parquet"
API_URL = "https://www.courtlistener.com/api/rest/v4/search/"

LITIGATION_QUERIES = ["uptier priming credit agreement", "drop-down financing lender liability", "liability management exercise lender"]


def scrape_litigation(session: CachedSession, queries: list[str] | None = None, max_results_per_query: int = 100) -> pd.DataFrame:
    queries = queries or LITIGATION_QUERIES
    rows = []
    for query in queries:
        result = session.get(API_URL, params={"q": query, "type": "r"})
        if result.status != 200:
            logger.warning("CourtListener query %r failed (status %d)", query, result.status)
            continue
        payload = result.json()
        for item in payload.get("results", [])[:max_results_per_query]:
            rows.append({
                "query": query, "case_name": item.get("caseName"), "court": item.get("court"),
                "date_filed": item.get("dateFiled"), "docket_number": item.get("docketNumber"),
                "absolute_url": f"https://www.courtlistener.com{item.get('absolute_url', '')}" if item.get("absolute_url") else None,
            })
        logger.info("CourtListener %r: %d results (total available: %s)", query, len(payload.get("results", [])), payload.get("count"))
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    session = CachedSession()
    df = scrape_litigation(session)
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[API_URL], scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.future.scrape_litigation",
        notes="Query terms are the well-known public terms for the LME litigation wave, not cross-referenced from a "
              "landmark-case-name discovery step against the news/ratings corpora (documented next step).",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
