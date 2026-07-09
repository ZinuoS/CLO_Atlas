"""Management vs. analyst tone divergence exhibits (Section 6) — degrades
gracefully. Depends on analysis_insider_tone.py, empty because
scrape_transcripts.py is stubbed (see docs/excluded_sources.md).
"""
from __future__ import annotations

import logging

import config
from src.common.cache import read_parquet

logger = logging.getLogger("clo_atlas.sentiment.viz_tone")

TONE_PATH = config.FINAL_DIR / "transcript_tone_divergence.parquet"


def viz_tone_divergence():
    df = read_parquet(TONE_PATH)
    if df.empty:
        logger.warning("no transcript tone data available (see docs/excluded_sources.md); "
                        "skipping viz_tone_divergence")
        return None
    logger.warning("tone data present but no chart implemented yet")
    return None


def run():
    viz_tone_divergence()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
