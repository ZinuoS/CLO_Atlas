"""US CLO/ABS issuance statistics (Section 4) — STUBBED.

SIFMA's download link routes through a HubSpot lead-gen form
(share.hsforms.com), not a direct file, and a previously-known direct
`.xlsx` path under wp-content/uploads now 404s (site rebuilt on Next.js).
See docs/excluded_sources.md — automating a marketing form isn't in the
spirit of polite public scraping even though there's no login/paywall.

`run()` is the documented entry point analysis_issuance.py expects, kept
stubbed rather than worked around.
"""
from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger("clo_atlas.official.scrape_sifma")


def run() -> pd.DataFrame:
    logger.warning(
        "scrape_sifma.py is stubbed — SIFMA's issuance-statistics download sits behind a "
        "HubSpot lead-gen form, not a direct file. See docs/excluded_sources.md."
    )
    return pd.DataFrame(columns=["period", "new_issue_usd", "refi_usd", "reset_usd"])


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
