"""Bank holdings of structured products vs. capital (Section 4) — degrades
gracefully to empty. Depends on scrape_ffiec.py, which is stubbed (see that
module's docstring for why: an ASP.NET WebForms postback plus no CLO-specific
line item in Call Report schedules). Kept as a real module with the
documented interface analysis layers share, not deleted, so wiring a future
FFIEC integration only means filling in scrape_ffiec.run().
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.official import scrape_ffiec

logger = logging.getLogger("clo_atlas.official.analysis_banks")

OUT_PATH = config.FINAL_DIR / "bank_structured_product_holdings.parquet"


def top_bank_holders() -> pd.DataFrame:
    raw = scrape_ffiec.run()
    if raw.empty:
        logger.warning("no FFIEC data available; top_bank_holders is empty (see scrape_ffiec.py docstring)")
        return pd.DataFrame(columns=["bank", "period", "structured_product_holdings", "pct_of_tier1_capital"])
    return raw


def run() -> pd.DataFrame:
    df = top_bank_holders()
    write_parquet(df, OUT_PATH, Provenance(parser="src.official.analysis_banks.top_bank_holders", source_urls=[]))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
