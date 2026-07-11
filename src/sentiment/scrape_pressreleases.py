"""CLO new-issue pricing tape — classified out of the headline corpus
scrape_news_rss.py already collects, rather than a second network scrape.

PR Newswire and Business Wire (both public, no login) already show up as
`source` values in data/interim/news_headlines.parquet because Google News
indexes them; a dedicated PR Newswire/Business Wire site search would just
duplicate that content through a different door. This module instead
classifies the existing corpus for pricing-announcement language ("prices
$XXX million CLO", "successfully priced <deal>") and extracts manager, deal
name, and size where the headline states them — a free, timestamped
new-issue tape, doubling as a cross-check on SIFMA (gated, see
docs/excluded_sources.md) and giving deal-level grain Section 4's official
issuance data lacks.

Same accretion limitation as scrape_news_rss.py: Google News RSS only
surfaces a rolling recent window, so historical depth builds up only from
running this repeatedly (a `make news` cadence), not a single backfill.
"""
from __future__ import annotations

import logging
import re

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.sentiment.scrape_pressreleases")

HEADLINES_PATH = config.INTERIM_DIR / "news_headlines.parquet"
OUT_PATH = config.INTERIM_DIR / "clo_pricing_tape.parquet"

_PRICE_PATTERN = re.compile(
    r"(?P<manager>[A-Z][\w&.'\- ]{2,40}?)\s+(?:Successfully\s+)?Prices?d?\s+"
    r"(?:(?P<deal>[A-Z0-9][\w.\-()]*(?:\s+[A-Z0-9][\w.\-()]*){0,4}?),?\s+)?"
    r"(?:A\s+)?\$(?P<size>[\d,.]+)\s*(?P<unit>Million|Billion|Mln|Bn|MM)",
    re.IGNORECASE,
)


def classify_pricing_announcements(headlines: pd.DataFrame) -> pd.DataFrame:
    if headlines.empty:
        return pd.DataFrame(columns=["title", "source", "published", "manager", "deal", "size_usd_millions"])
    is_clo_related = headlines["title"].str.contains(r"\bCLO\b|collateralized loan obligation", case=False, regex=True, na=False)
    # Not strictly limited to _PR_SOURCES: TradingView and other outlets
    # frequently re-syndicate the same PR Newswire/Business Wire release
    # text verbatim, and the pricing-announcement regex below is precise
    # enough on its own to not need a source-level prefilter.
    candidates = headlines[is_clo_related].copy()

    rows = []
    for _, row in candidates.iterrows():
        match = _PRICE_PATTERN.search(row["title"])
        if not match:
            continue
        size = float(match.group("size").replace(",", ""))
        unit = match.group("unit").lower()
        size_millions = size * 1000 if unit in ("billion", "bn") else size
        rows.append({
            "title": row["title"], "source": row["source"], "published": row["published"],
            "manager": match.group("manager").strip(),
            "deal": match.group("deal").strip() if match.group("deal") else None,
            "size_usd_millions": size_millions,
        })
    out = pd.DataFrame(rows)
    logger.info("classified %d/%d CLO-related headlines as pricing announcements", len(out), len(candidates))
    return out


def run() -> pd.DataFrame:
    if not HEADLINES_PATH.exists():
        logger.warning("no news_headlines.parquet cached; run scrape_news_rss.py first")
        return pd.DataFrame()
    headlines = read_parquet(HEADLINES_PATH)
    tape = classify_pricing_announcements(headlines)
    write_parquet(tape, OUT_PATH, Provenance(
        source_urls=[], parser="src.sentiment.scrape_pressreleases",
        notes="Classified from data/interim/news_headlines.parquet (Google News RSS, which itself indexes PR Newswire/"
              "Business Wire/GlobeNewswire), not a separate network scrape. Regex-parsed manager/deal/size; misses "
              "announcements phrased differently than 'X Prices $Y Million CLO Z'.",
    ))
    return tape


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
