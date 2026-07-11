"""MM/private-credit share of CLO composition over time (Part C) — from the
manager-shelf-keyword proxy (`scrape_mm_share.py`), NOT the originally
planned market-wide BSL-vs-MM new-issue share joined against a presale-
vocabulary series (Section 5's presale corpus is empty — see that module's
docstring and docs/excluded_sources.md). This is two funds' own CLO-equity
holdings composition over their own filing history, a much narrower lens
than "the marginal CLO issued market-wide," and labeled as such.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.future.analysis_composition_shift")

MM_SHARE_PATH = config.INTERIM_DIR / "future_mm_share_proxy.parquet"

OUT_TREND = config.FINAL_DIR / "composition_shift_mm_trend.parquet"


def mm_share_trend() -> pd.DataFrame:
    if not MM_SHARE_PATH.exists():
        logger.warning("no mm_share proxy data cached; mm_share_trend is empty")
        return pd.DataFrame(columns=["fund", "period", "mm_share"])
    df = read_parquet(MM_SHARE_PATH)
    if df.empty:
        return pd.DataFrame(columns=["fund", "period", "mm_share"])
    mm_rows = df[df["is_mm"] == True][["fund", "period", "share"]].rename(columns={"share": "mm_share"})  # noqa: E712
    return mm_rows.sort_values(["fund", "period"])


def run() -> pd.DataFrame:
    trend = mm_share_trend()
    write_parquet(trend, OUT_TREND, Provenance(
        parser="src.future.analysis_composition_shift.mm_share_trend", source_urls=[],
        notes="Two funds' own CLO-equity holdings, manager-shelf-keyword proxy — not a market-wide new-issue share.",
    ))
    logger.info("mm_share_trend=%d fund-period rows", len(trend))
    return trend


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
