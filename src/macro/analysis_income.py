"""Same-rating yield comparison and carry-per-unit-duration (appendix/Q&A
material for the macro opener — income exhibits, lowest priority per the
build order, but still real, computed exhibits).

The AAA CLO discount-margin proxy called for in the brief doesn't exist:
Section 1's tranche panel (data/final/etf_aaa_price_index.parquet) only has
a price index, not a spread/DM figure, so — exactly as the brief allows —
this uses price-based dispersion (data/final/etf_aaa_mark_dispersion.parquet)
as the CLO AAA proxy instead, and says so on the chart.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.macro.analysis_income")

FRED_PATH = config.INTERIM_DIR / "macro_fred_series.parquet"
AAA_DISPERSION_PATH = config.FINAL_DIR / "etf_aaa_mark_dispersion.parquet"
CHARACTERISTICS_PATH = config.INTERIM_DIR / "macro_fund_characteristics.parquet"

OUT_SPREAD_COMPARISON = config.FINAL_DIR / "macro_spread_comparison.parquet"
OUT_AAA_DISPERSION_PROXY = config.FINAL_DIR / "macro_aaa_dispersion_proxy.parquet"
OUT_CARRY_PER_DURATION = config.FINAL_DIR / "macro_carry_per_duration.parquet"

SPREAD_SERIES_LABELS = {"AAA_OAS": "AAA corporate", "BBB_OAS": "BBB corporate", "IG_OAS": "IG corporate (broad)", "HY_OAS": "High yield"}


def spread_comparison() -> pd.DataFrame:
    """Latest same-rating spread-over-risk-free per market, from FRED OAS series."""
    if not FRED_PATH.exists():
        return pd.DataFrame(columns=["market", "oas_pct", "as_of"])
    fred = read_parquet(FRED_PATH)
    fred["date"] = pd.to_datetime(fred["date"])
    rows = []
    for series, label in SPREAD_SERIES_LABELS.items():
        sub = fred[(fred["series"] == series)].dropna(subset=["value"]).sort_values("date")
        if sub.empty:
            continue
        rows.append({"market": label, "oas_pct": sub["value"].iloc[-1], "as_of": sub["date"].iloc[-1]})
    return pd.DataFrame(rows).sort_values("oas_pct")


def aaa_dispersion_proxy() -> pd.DataFrame:
    """CLO AAA cross-sectional mark dispersion (price-based proxy for a
    discount-margin series that doesn't exist in this project's data)."""
    if not AAA_DISPERSION_PATH.exists():
        logger.warning("no etf_aaa_mark_dispersion.parquet cached; run src.etf.analysis_tranche_panel first")
        return pd.DataFrame(columns=["date", "median_price", "iqr", "p10", "p90"])
    return read_parquet(AAA_DISPERSION_PATH)


def carry_per_duration() -> pd.DataFrame:
    """Yield / effective duration per fund — the "income without the
    duration bill" exhibit. All figures scraped from each fund's own
    overview page (src.macro.scrape_returns.scrape_fund_characteristics)."""
    if not CHARACTERISTICS_PATH.exists():
        logger.warning("no macro_fund_characteristics.parquet cached; run src.macro.scrape_returns first")
        return pd.DataFrame(columns=["ticker", "yield_pct", "effective_duration_years", "carry_per_duration", "yield_label"])
    df = read_parquet(CHARACTERISTICS_PATH).dropna(subset=["yield_pct", "effective_duration_years"])
    # JAAA's duration is a few hundredths of a year; floor it so the ratio
    # doesn't blow up into a meaningless spike from near-zero-duration noise.
    floor = 0.05
    df["carry_per_duration"] = df["yield_pct"] / df["effective_duration_years"].clip(lower=floor)
    return df.sort_values("carry_per_duration")


def run() -> dict[str, pd.DataFrame]:
    spreads = spread_comparison()
    write_parquet(spreads, OUT_SPREAD_COMPARISON, Provenance(parser="src.macro.analysis_income.spread_comparison", source_urls=[]))

    dispersion = aaa_dispersion_proxy()
    write_parquet(dispersion, OUT_AAA_DISPERSION_PROXY, Provenance(
        parser="src.macro.analysis_income.aaa_dispersion_proxy", source_urls=[],
        notes="Price-based dispersion, reused from Section 1's tranche panel — not a discount-margin series (none exists in this project's data).",
    ))

    carry = carry_per_duration()
    write_parquet(carry, OUT_CARRY_PER_DURATION, Provenance(
        parser="src.macro.analysis_income.carry_per_duration", source_urls=[],
        notes="Yield definitions differ by issuer (iShares: Yield to Maturity; Janus Henderson/JAAA: Yield to Worst) — labeled per-fund, not blended.",
    ))

    logger.info("spreads=%d markets, aaa_dispersion=%d dates, carry=%d funds", len(spreads), len(dispersion), len(carry))
    return {"spreads": spreads, "aaa_dispersion": dispersion, "carry": carry}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
