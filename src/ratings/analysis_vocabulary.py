"""Presale-text vocabulary drift — cov-lite, LME, ESG mention rates, LM
sentiment (Section 5) — degrades gracefully to empty. Depends on
scrape_presales.py, which is stubbed — see docs/excluded_sources.md and
src/ratings/scrape_presales.py's docstring.

The analysis this would run is fully implemented and real in
src/common/text.py (mention_rate_per_1000, score_lm, collocates) — it is
only the presale corpus itself that's unavailable here.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.text import mention_rate_per_1000
from src.ratings import scrape_presales

logger = logging.getLogger("clo_atlas.ratings.analysis_vocabulary")

OUT_PATH = config.FINAL_DIR / "ratings_presale_vocabulary.parquet"

TERMS = ["cov-lite", "EBITDA add-back", "ESG", "liability management", "priming",
         "drop-down", "uptier", "recovery rate", "CCC bucket", "reinvestment",
         "workout", "loss mitigation loan"]


def presale_vocabulary() -> pd.DataFrame:
    raw = scrape_presales.run()
    if raw.empty:
        logger.warning("no presale corpus available; presale_vocabulary is empty")
        return pd.DataFrame(columns=["date", "agency", "deal", "term", "mentions_per_1000_tokens"])
    rows = []
    for _, row in raw.iterrows():
        rates = mention_rate_per_1000(row["raw_text"], TERMS)
        for term, rate in rates.items():
            rows.append({"date": row["date"], "agency": row["agency"], "deal": row["deal"],
                         "term": term, "mentions_per_1000_tokens": rate})
    return pd.DataFrame(rows)


def run() -> pd.DataFrame:
    df = presale_vocabulary()
    write_parquet(df, OUT_PATH, Provenance(parser="src.ratings.analysis_vocabulary.presale_vocabulary", source_urls=[]))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
