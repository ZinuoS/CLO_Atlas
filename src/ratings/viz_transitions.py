"""Rating-transition exhibits (Section 5) — degrade gracefully.

Depends on analysis_transitions.py, which is empty because scrape_actions.py
is stubbed (S&P/Fitch access wall — see docs/excluded_sources.md). Kept as a
real module with the pattern every viz module follows; produces no figure
and logs why rather than emitting an empty/broken chart.
"""
from __future__ import annotations

import logging

import config
from src.common.cache import read_parquet

logger = logging.getLogger("clo_atlas.ratings.viz_transitions")

MONTHLY_PATH = config.FINAL_DIR / "ratings_transitions_monthly.parquet"
IMPAIRMENTS_PATH = config.FINAL_DIR / "ratings_senior_impairments.parquet"


def viz_transition_diverging_bar():
    df = read_parquet(MONTHLY_PATH)
    if df.empty:
        logger.warning("no rating-transition data available (S&P/Fitch gated — see docs/excluded_sources.md); "
                        "skipping viz_transition_diverging_bar")
        return None
    logger.warning("transition data present but no chart implemented yet")
    return None


def viz_senior_impairment_record():
    df = read_parquet(IMPAIRMENTS_PATH)
    if df.empty:
        logger.warning("no impairment data available (S&P/Fitch gated — see docs/excluded_sources.md); "
                        "skipping viz_senior_impairment_record — this is the signature "
                        "'zero AAA impairments' exhibit and needs a real rating-action feed")
        return None
    logger.warning("impairment data present but no chart implemented yet")
    return None


def run():
    viz_transition_diverging_bar()
    viz_senior_impairment_record()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
