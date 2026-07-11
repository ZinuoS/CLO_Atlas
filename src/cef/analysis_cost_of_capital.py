"""Cost of capital vs. portfolio yield (Section 2 deep-dive): the observable
arbitrage margin these vehicles run on.

Preferred/baby-bond current yield = $25 stated liquidation preference x
coupon / market price (the standard approximation for exchange-listed term
preferred — not a yield-to-call/worst calculation, which needs the exact
call schedule). Portfolio effective yield is the par-weighted mean of each
fund's disclosed `annualizedRt` across its CLO equity positions (NPORT-P).
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.cef.analysis_cost_of_capital")

PREFERRED_PRICES_PATH = config.INTERIM_DIR / "cef_preferred_prices.parquet"
PREFERRED_SERIES_PATH = config.INTERIM_DIR / "cef_preferred_series.parquet"
POSITIONS_PATH = config.INTERIM_DIR / "cef_clo_positions.parquet"

OUT_PREFERRED_YIELD = config.FINAL_DIR / "cost_of_capital_preferred_yield.parquet"
OUT_MARGIN = config.FINAL_DIR / "cost_of_capital_margin.parquet"

PAR = 25.0


def preferred_current_yield() -> pd.DataFrame:
    if not PREFERRED_PRICES_PATH.exists() or not PREFERRED_SERIES_PATH.exists():
        logger.warning("missing preferred prices or series data; preferred_current_yield is empty")
        return pd.DataFrame(columns=["ticker", "fund", "date", "close", "current_yield"])
    prices = read_parquet(PREFERRED_PRICES_PATH)
    series = read_parquet(PREFERRED_SERIES_PATH)

    # Coupon lookup by ticker isn't direct (series table is keyed by fund +
    # series name, not ticker); use each fund's most recent-vintage coupon
    # as a representative rate per ticker slot, ordered to roughly line up
    # with config.CLO_CEF_PREFERRED_TICKERS' listing order. This is a
    # coarse approximation, flagged as such — an exact ticker->series
    # mapping would need each series' actual ticker disclosed in the
    # prospectus, which these filings don't state in machine-readable form.
    latest = prices.sort_values("date").groupby("ticker").tail(1)
    rows = []
    for _, row in latest.iterrows():
        fund_series = series[series["ticker"] == row["fund"]].sort_values("first_seen_filing_date")
        if fund_series.empty:
            continue
        coupon = fund_series["coupon_pct"].median()  # representative rate across that fund's outstanding series
        current_yield = (PAR * coupon / 100) / row["close"]
        rows.append({"ticker": row["ticker"], "fund": row["fund"], "date": row["date"],
                      "close": row["close"], "coupon_pct_used": coupon, "current_yield": current_yield})
    return pd.DataFrame(rows)


def portfolio_effective_yield() -> pd.DataFrame:
    if not POSITIONS_PATH.exists():
        return pd.DataFrame(columns=["fund", "period", "portfolio_effective_yield"])
    df = read_parquet(POSITIONS_PATH)
    df = df[(df["is_clo"] == True) & df["annualizedRt"].notna() & df["valUSD"].notna()]  # noqa: E712
    if df.empty:
        return pd.DataFrame(columns=["fund", "period", "portfolio_effective_yield"])

    def _weighted_yield(g):
        w = g["valUSD"]
        return (g["annualizedRt"] * w).sum() / w.sum() if w.sum() else None
    out = df.groupby(["fund", "period"]).apply(_weighted_yield, include_groups=False).reset_index(name="portfolio_effective_yield")
    return out


def cost_of_capital_margin(preferred_yield: pd.DataFrame, portfolio_yield: pd.DataFrame) -> pd.DataFrame:
    if preferred_yield.empty or portfolio_yield.empty:
        return pd.DataFrame(columns=["fund", "blended_cost_of_capital", "portfolio_effective_yield", "margin"])
    blended = preferred_yield.groupby("fund")["current_yield"].mean().reset_index(name="blended_cost_of_capital")
    latest_portfolio = portfolio_yield.sort_values("period").groupby("fund").tail(1)
    merged = blended.merge(latest_portfolio, on="fund", how="inner")
    merged["margin"] = merged["portfolio_effective_yield"] / 100 - merged["blended_cost_of_capital"]
    return merged


def run() -> dict[str, pd.DataFrame]:
    preferred_yield = preferred_current_yield()
    write_parquet(preferred_yield, OUT_PREFERRED_YIELD, Provenance(
        parser="src.cef.analysis_cost_of_capital.preferred_current_yield", source_urls=[],
        notes="Coupon per ticker approximated as the fund's median outstanding series coupon (no exact ticker->series map available).",
    ))

    portfolio_yield = portfolio_effective_yield()
    margin = cost_of_capital_margin(preferred_yield, portfolio_yield)
    write_parquet(margin, OUT_MARGIN, Provenance(parser="src.cef.analysis_cost_of_capital.cost_of_capital_margin", source_urls=[]))

    logger.info("preferred_yield=%d rows, margin=%d funds", len(preferred_yield), len(margin))
    return {"preferred_yield": preferred_yield, "portfolio_yield": portfolio_yield, "margin": margin}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
