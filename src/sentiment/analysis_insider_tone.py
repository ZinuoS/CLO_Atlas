"""Management vs. analyst tone divergence from earnings-call transcripts
(Section 6) — degrades gracefully. Depends on scrape_transcripts.py, which
is stubbed (no shared cross-issuer structure to exploit — see that module's
docstring and docs/excluded_sources.md).
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.sentiment import scrape_transcripts

logger = logging.getLogger("clo_atlas.sentiment.analysis_insider_tone")

OUT_PATH = config.FINAL_DIR / "transcript_tone_divergence.parquet"


def tone_divergence() -> pd.DataFrame:
    raw = scrape_transcripts.run()
    if raw.empty:
        logger.warning("no transcript data available; tone_divergence is empty (see scrape_transcripts.py docstring)")
        return pd.DataFrame(columns=["company", "quarter", "management_sentiment", "analyst_sentiment", "divergence"])
    return raw


def run() -> pd.DataFrame:
    df = tone_divergence()
    write_parquet(df, OUT_PATH, Provenance(parser="src.sentiment.analysis_insider_tone.tone_divergence", source_urls=[]))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
