"""CLO issuance-cycle exhibit (Section 4) — degrades gracefully.

Depends on analysis_issuance.py, which is empty because scrape_sifma.py is
stubbed (gated data source — see docs/excluded_sources.md). Kept as a real
module with the pattern every viz module follows; produces no figure and
logs why rather than emitting an empty/broken chart.
"""
from __future__ import annotations

import logging

import config
from src.common.cache import read_parquet

logger = logging.getLogger("clo_atlas.official.viz_issuance")

ISSUANCE_PATH = config.FINAL_DIR / "clo_issuance_cycle.parquet"


def viz_issuance_by_type():
    df = read_parquet(ISSUANCE_PATH)
    if df.empty:
        logger.warning("no issuance data available (SIFMA gated — see docs/excluded_sources.md); "
                        "skipping viz_issuance_by_type")
        return None
    logger.warning("issuance data present but no chart implemented yet")
    return None


def run():
    viz_issuance_by_type()


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
