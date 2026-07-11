"""Middle-market vs. broadly-syndicated CLO classification (Part C:
composition shift) — NOT from the Section 5 presale corpus the original
plan called for: that corpus is empty (S&P is Akamai-walled, Fitch's
listing pages are client-rendered — both already logged in
docs/excluded_sources.md), so there is no presale text to classify.

Instead this classifies deal shelf names already scraped for the CEF deep-
dive (`data/interim/cef_clo_positions.parquet`, from NPORT-P) using a small
hand-curated list of manager shelves publicly known to run middle-market
CLO programs (e.g. PennantPark, Flat Rock, Monroe, Golub, NMFC/New Mountain,
Franklin BSP, AB Private Credit). This is a coarse, keyword-based
classification of a DIFFERENT universe (two funds' actual CLO-equity
holdings, not the full market's new-issue count) — not a substitute for
the originally planned market-wide BSL-vs-MM issuance share, which remains
a gap and is reported as one, not quietly worked around.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.future.scrape_mm_share")

POSITIONS_PATH = config.INTERIM_DIR / "cef_clo_positions.parquet"
OUT_PATH = config.INTERIM_DIR / "future_mm_share_proxy.parquet"

# Hand-curated, publicly known middle-market-focused CLO shelf name
# fragments (case-insensitive substring match against the deal name).
MM_SHELF_KEYWORDS = [
    "pennantpark", "flat rock", "monroe capital", "golub", "new mountain",
    "nmfc", "franklin bsp", "bsp", "ab private credit", "audax", "crescent private",
    "mm cbdo", "middle market",
]


def classify_mm_share() -> pd.DataFrame:
    if not POSITIONS_PATH.exists():
        logger.warning("no CLO position data cached; classify_mm_share is empty")
        return pd.DataFrame(columns=["fund", "period", "is_mm", "total_valUSD", "share"])
    df = read_parquet(POSITIONS_PATH)
    df = df[df["is_clo"] == True].copy()  # noqa: E712
    if df.empty:
        return pd.DataFrame(columns=["fund", "period", "is_mm", "total_valUSD", "share"])

    name_lower = df["name"].fillna("").str.lower()
    df["is_mm"] = name_lower.apply(lambda n: any(kw in n for kw in MM_SHELF_KEYWORDS))
    by_group = df.groupby(["fund", "period", "is_mm"]).agg(total_valUSD=("valUSD", "sum")).reset_index()
    totals = by_group.groupby(["fund", "period"])["total_valUSD"].transform("sum")
    by_group["share"] = by_group["total_valUSD"] / totals
    return by_group


def run() -> pd.DataFrame:
    df = classify_mm_share()
    write_parquet(df, OUT_PATH, Provenance(
        parser="src.future.scrape_mm_share.classify_mm_share", source_urls=[],
        notes="Proxy classification of two funds' CLO-equity holdings by manager-shelf keyword, NOT the originally "
              "planned market-wide BSL-vs-MM new-issue share (Section 5 presale corpus is empty — see module docstring).",
    ))
    logger.info("mm_share_proxy=%d fund-period-is_mm rows", len(df))
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
