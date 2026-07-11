"""arXiv API (free, no key) — academic-attention series for CLO-related
research, titles/abstracts/dates only.

SSRN has no public search API (its search is a JS-rendered page with no
discovered stable JSON endpoint) and RePEc's IDEAS search likewise renders
client-side for query results — both logged as gaps in
docs/excluded_sources.md rather than guessed at; arXiv covers the
quantitative-finance side of this literature reasonably well on its own.
"""
from __future__ import annotations

import datetime as dt
import logging

import feedparser
import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.sentiment.scrape_ssrn_arxiv")

OUT_PATH = config.INTERIM_DIR / "arxiv_papers.parquet"
API_URL = "https://export.arxiv.org/api/query"

ARXIV_QUERIES = ["collateralized loan obligation", "CLO tranche", "leveraged loan securitization"]


def scrape_arxiv(session: CachedSession, queries: list[str] | None = None, max_results: int = 50) -> pd.DataFrame:
    queries = queries or ARXIV_QUERIES
    rows = []
    for query in queries:
        result = session.get(API_URL, params={"search_query": f"all:{query}", "max_results": max_results})
        if result.status != 200:
            logger.warning("arXiv query %r failed (status %d)", query, result.status)
            continue
        parsed = feedparser.parse(result.content)
        for entry in parsed.entries:
            rows.append({
                "query": query, "title": entry.get("title", "").replace("\n", " ").strip(),
                "published": entry.get("published"), "authors": ", ".join(a.name for a in entry.get("authors", [])),
                "summary": entry.get("summary", "").replace("\n", " ").strip()[:500],
                "link": entry.get("link"),
            })
        logger.info("arXiv %r: %d papers", query, len(parsed.entries))
    return pd.DataFrame(rows).drop_duplicates(subset=["link"]) if rows else pd.DataFrame(rows)


def run() -> pd.DataFrame:
    session = CachedSession()
    df = scrape_arxiv(session)
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[API_URL], scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.sentiment.scrape_ssrn_arxiv",
        notes="arXiv only — SSRN/RePEc search both render client-side with no discovered stable API (see docs/excluded_sources.md).",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
