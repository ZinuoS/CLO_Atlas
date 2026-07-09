"""Bank call-report structured-product holdings (Section 4) — STUBBED.

Two separate obstacles, neither a paywall:

1. FFIEC's bulk Call Report download (cdr.ffiec.gov/public/PWS/DownloadBulkData.aspx)
   is an ASP.NET WebForms page: the file comes back via a __VIEWSTATE/
   __EVENTVALIDATION postback, not a predictable GET URL. Doable (third-party
   libraries like github.com/call-report/data-collector replicate the
   postback), but a meaningfully larger build than a direct-URL scraper.
2. Even with the bulk file in hand, Call Report schedules don't isolate CLO
   holdings as their own line item — the closest available granularity is a
   broader "structured financial products" category (which bundles CLOs with
   other ABS/CDOs), so the payoff is a proxy, not a clean CLO figure.

Logged to docs/excluded_sources.md rather than worked around with a fragile
postback replica for uncertain payoff. If this becomes worth the investment
later, `run()` is the documented entry point analysis_banks.py expects.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("clo_atlas.official.scrape_ffiec")


def run() -> pd.DataFrame:
    logger.warning(
        "scrape_ffiec.py is stubbed — FFIEC bulk Call Report data requires replicating an "
        "ASP.NET WebForms postback and doesn't isolate CLO holdings as a distinct line item "
        "even once fetched. See docs/excluded_sources.md and this module's docstring."
    )
    return pd.DataFrame(columns=["bank", "period", "structured_product_holdings"])


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
