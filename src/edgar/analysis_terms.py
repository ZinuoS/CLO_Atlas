"""Spread and coupon distributions over time from BDC SOI terms (Section 3).

NPORT/BDC disclosures don't carry a clean "LIBOR floor" field, so the
mission brief's "disappearance of LIBOR floors" needs text-mining a
different source (rating-agency presale text, which is gated — see Section
5) to do properly; this reports what IS directly disclosed: coupon and
spread distributions by period, which still shows the broadly-syndicated-to-
SOFR transition story via spread-level drift.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.edgar.analysis_terms")

BDC_SOI_PATH = config.INTERIM_DIR / "bdc_soi_positions.parquet"

OUT_SPREAD = config.FINAL_DIR / "edgar_spread_distribution.parquet"
OUT_MATURITY = config.FINAL_DIR / "edgar_maturity_wall.parquet"


def spread_distribution_by_period() -> pd.DataFrame:
    if not BDC_SOI_PATH.exists():
        logger.warning("no BDC SOI data cached; run scrape_bdc_soi.py first")
        return pd.DataFrame(columns=["period", "median_spread", "p25", "p75", "n"])
    soi = read_parquet(BDC_SOI_PATH).dropna(subset=["spread"])
    soi = soi[soi["spread"].between(0, 15)]  # spreads are in percentage points; >15 is a data artifact, not a real loan spread
    g = soi.groupby("period")["spread"].agg(
        median_spread="median", p25=lambda s: s.quantile(0.25), p75=lambda s: s.quantile(0.75), n="count"
    ).reset_index()
    return g


def maturity_wall() -> pd.DataFrame:
    # BDC SOI's XBRL-rendered fragment doesn't carry maturity date as a
    # clean scalar fact the way it carries coupon/spread/fair value (it's in
    # the free-text investment identifier in some filers, not structured) —
    # logged as a gap rather than parsed unreliably from free text.
    logger.warning("maturity date isn't a clean structured field in the BDC SOI XBRL fragment; "
                    "maturity_wall is empty rather than guessed from free text")
    return pd.DataFrame(columns=["maturity_year", "count", "total_fair_value"])


def run() -> dict[str, pd.DataFrame]:
    spread = spread_distribution_by_period()
    write_parquet(spread, OUT_SPREAD, Provenance(parser="src.edgar.analysis_terms.spread_distribution_by_period", source_urls=[]))

    maturity = maturity_wall()
    write_parquet(maturity, OUT_MATURITY, Provenance(parser="src.edgar.analysis_terms.maturity_wall", source_urls=[]))

    logger.info("spread_distribution=%d periods, maturity_wall=%d rows", len(spread), len(maturity))
    return {"spread": spread, "maturity": maturity}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
