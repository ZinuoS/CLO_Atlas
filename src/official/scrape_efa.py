"""CLO holder composition (Section 4).

Not a live scraper in the usual sense — see config.FED_CLO_HOLDER_CITATION
for why: the Fed's Enhanced Financial Accounts project has no dedicated CLO
page, and the Financial Accounts (Z.1) "Issuers of ABS" sector series
aggregate all ABS issuers, not CLOs specifically (checked directly against
federalreserve.gov 2026-07-09). The one genuinely CLO-specific breakdown the
Fed has published — "Who Owns U.S. CLO Securities? An Update by Tranche"
(2020) — exists only as prose/table-images in a FEDS Note with no linked
machine-readable file.

Rather than either fabricate a scraped series or silently skip the "who
holds it" story, this module formalizes the Fed's own published numbers as a
cited, dated dataset. Every downstream table built from it carries
to_verify=True: this is Section 4's canonical example of the project's
VERIFIED-vs-TO-VERIFY doctrine, not a live series, and it will not update on
its own — if the Fed publishes a newer breakdown, config.FED_CLO_HOLDER_CITATION
needs a manual update, which is itself logged via the provenance sidecar.
"""
from __future__ import annotations

import datetime as dt
import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet

logger = logging.getLogger("clo_atlas.official.scrape_efa")

OUT_PATH = config.INTERIM_DIR / "fed_clo_holders_citation.parquet"


def run() -> pd.DataFrame:
    citation = config.FED_CLO_HOLDER_CITATION
    holdings = citation["holdings_by_investor_type_usd_millions"]
    total = sum(holdings.values())
    df = pd.DataFrame([
        {"investor_type": k, "amount_usd_millions": v, "share": v / total, "to_verify": True}
        for k, v in holdings.items()
    ]).sort_values("amount_usd_millions", ascending=False).reset_index(drop=True)

    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[citation["source_url"]],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.official.scrape_efa",
        notes=f"Hand-transcribed from '{citation['source_title']}', as of {citation['as_of']}. "
              f"Not a live series — see module docstring. {citation['note']}",
    ))
    logger.info("wrote %d holder-type rows (TO-VERIFY, as of %s) to %s", len(df), citation["as_of"], OUT_PATH)
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
