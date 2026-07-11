"""Institutional ownership floor vs. premium volatility (Section 2 deep-dive)
— what a retail-heavy shareholder register implies for premium persistence.

`institutional_floor` sums the latest 13G filing's percent-of-class per
filer per fund — a LOWER BOUND (only >5% holders are visible via 13G), not
a complete institutional share. The retail-stickiness hypothesis (thinner
institutional ownership -> more persistent premium/discount swings, since
retail flow is less arbitrage-disciplined) is tested as a plain descriptive
comparison across funds, not a fitted model.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.cef.analysis_ownership")

OWNERSHIP_PATH = config.INTERIM_DIR / "cef_13g_ownership.parquet"
PRICES_PATH = config.INTERIM_DIR / "cef_prices.parquet"

OUT_FLOOR = config.FINAL_DIR / "ownership_institutional_floor.parquet"
OUT_VS_VOLATILITY = config.FINAL_DIR / "ownership_vs_price_volatility.parquet"


def institutional_floor() -> pd.DataFrame:
    """Sum of percent-of-class across DISTINCT recent 13G share-count
    values per fund (a proxy for distinct filers: the filer-name field in
    these filings' cover pages didn't extract reliably via regex — see
    scrape_13f_ownership.py — so distinct `shares_owned` values within a
    ~2-year trailing window stand in for distinct reporting persons; a
    single filer amending its own stake would still show as one value
    unless it changed the share count, which is the common case)."""
    if not OWNERSHIP_PATH.exists():
        logger.warning("no 13G ownership data cached; institutional_floor is empty")
        return pd.DataFrame(columns=["ticker", "institutional_floor_pct", "n_filers"])
    df = read_parquet(OWNERSHIP_PATH).dropna(subset=["percent_of_class", "shares_owned"])
    if df.empty:
        return pd.DataFrame(columns=["ticker", "institutional_floor_pct", "n_filers"])
    df["filing_date"] = pd.to_datetime(df["filing_date"])
    cutoff = df["filing_date"].max() - pd.DateOffset(years=2)
    recent = df[df["filing_date"] >= cutoff]
    # Latest disclosure per distinct share count within the trailing window.
    latest = recent.sort_values("filing_date").groupby("shares_owned").tail(1)
    out = latest.groupby("ticker").agg(institutional_floor_pct=("percent_of_class", "sum"),
                                         n_filers=("shares_owned", "nunique")).reset_index()
    return out


def ownership_vs_price_volatility(floor: pd.DataFrame) -> pd.DataFrame:
    if floor.empty or not PRICES_PATH.exists():
        return pd.DataFrame(columns=["ticker", "institutional_floor_pct", "price_volatility_annualized"])
    prices = read_parquet(PRICES_PATH)
    rows = []
    for _, row in floor.iterrows():
        sub = prices[prices["ticker"] == row["ticker"]].sort_values("date")
        if len(sub) < 30:
            continue
        rets = sub["adj_close"].pct_change().dropna()
        vol = rets.std() * (252 ** 0.5)
        rows.append({"ticker": row["ticker"], "institutional_floor_pct": row["institutional_floor_pct"],
                      "price_volatility_annualized": vol})
    return pd.DataFrame(rows)


def run() -> dict[str, pd.DataFrame]:
    floor = institutional_floor()
    write_parquet(floor, OUT_FLOOR, Provenance(
        parser="src.cef.analysis_ownership.institutional_floor", source_urls=[],
        notes="Sum of latest 13G percent-of-class per filer — a lower bound on institutional ownership, not the complete share.",
    ))

    vs_vol = ownership_vs_price_volatility(floor)
    write_parquet(vs_vol, OUT_VS_VOLATILITY, Provenance(parser="src.cef.analysis_ownership.ownership_vs_price_volatility", source_urls=[]))

    logger.info("institutional_floor=%d funds, vs_volatility=%d funds", len(floor), len(vs_vol))
    return {"floor": floor, "vs_volatility": vs_vol}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
