"""CLO holder composition (Section 4).

Built entirely from config.FED_CLO_HOLDER_CITATION via scrape_efa.py — a
single dated (Dec 2018) breakdown, not a time series (see that module's
docstring for why no free source provides one). Every row here is TO-VERIFY:
an external figure quoted from a Fed publication, not computed in this repo.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.official.analysis_holders")

CITATION_PATH = config.INTERIM_DIR / "fed_clo_holders_citation.parquet"
OUT_PATH = config.FINAL_DIR / "clo_holder_composition.parquet"


def holder_composition() -> pd.DataFrame:
    if not CITATION_PATH.exists():
        logger.warning("no Fed CLO holder citation cached; run scrape_efa.py first")
        return pd.DataFrame(columns=["investor_type", "amount_usd_millions", "share", "to_verify"])
    df = read_parquet(CITATION_PATH)
    citation = config.FED_CLO_HOLDER_CITATION
    logger.info("holder composition as of %s (source: %s) — %d investor types, TO-VERIFY",
                citation["as_of"], citation["source_title"], len(df))
    return df


def run() -> pd.DataFrame:
    df = holder_composition()
    write_parquet(df, OUT_PATH, Provenance(
        parser="src.official.analysis_holders", source_urls=[config.FED_CLO_HOLDER_CITATION["source_url"]],
        notes="TO-VERIFY: single dated snapshot from a Fed publication, not a computed time series.",
    ))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
