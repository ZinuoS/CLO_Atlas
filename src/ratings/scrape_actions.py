"""S&P/Fitch CLO tranche rating-action press releases (Section 5) — STUBBED.

Both agencies checked directly 2026-07-09, neither is scrapable within this
project's "polite public scraping" bounds:

- **S&P Global Ratings**: the entire spglobal.com/ratings domain sits behind
  Akamai bot protection — even a bare `robots.txt` request returns HTTP 403
  regardless of a declared, honest User-Agent. Not a login wall; a hard deny.
- **Fitch Ratings**: reachable, but the rating-action listing/search pages
  are entirely client-rendered with no server-side HTML content and no
  discoverable JSON API in the page source. Fitch's own docs confirm
  programmatic access ("Feeds and API") is a paid product.

See docs/excluded_sources.md. `run()` is the documented entry point
analysis_transitions.py / analysis_vintage.py expect, kept stubbed rather
than worked around with headless-browser automation or a third-party mirror
of uncertain licensing (LSTA's Fitch commentary page).
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("clo_atlas.ratings.scrape_actions")


def run() -> pd.DataFrame:
    logger.warning(
        "scrape_actions.py is stubbed — S&P Global Ratings is behind an Akamai bot wall (403 even on "
        "robots.txt) and Fitch Ratings' rating-action pages are entirely client-rendered with no free "
        "API. See docs/excluded_sources.md."
    )
    return pd.DataFrame(columns=["date", "agency", "deal", "tranche", "action", "from_rating", "to_rating"])


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
