"""Presale vocabulary exhibits (Section 5) — degrades gracefully. Depends on
analysis_vocabulary.py, empty because scrape_presales.py is stubbed (see
docs/excluded_sources.md).
"""
from __future__ import annotations

import logging

import config
from src.common.cache import read_parquet

logger = logging.getLogger("clo_atlas.ratings.viz_vocabulary")

VOCAB_PATH = config.FINAL_DIR / "ratings_presale_vocabulary.parquet"


def viz_lme_term_frequency():
    df = read_parquet(VOCAB_PATH)
    if df.empty:
        logger.warning("no presale vocabulary data available (S&P/Fitch gated — see docs/excluded_sources.md); "
                        "skipping viz_lme_term_frequency — this is the signature LME-vocabulary-explosion "
                        "exhibit and needs a real presale corpus")
        return None
    logger.warning("vocabulary data present but no chart implemented yet")
    return None


def run():
    viz_lme_term_frequency()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
