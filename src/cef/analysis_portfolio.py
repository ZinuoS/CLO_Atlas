"""Disclosed CLO-equity portfolio economics from NPORT-P filings (Section 2).

Unlike most of this project's per-fund analyses, this one already has a real
multi-quarter time series on day one — NPORT-P filings are quarterly, and
scrape_filings.py pulls the four most recent per fund. NPORT doesn't disclose
cost basis or CCC%/OC-cushion at the position level, so "fair value / cost"
and credit-quality trajectories from the mission brief aren't available from
this source; weighted effective yield and position-level concentration are.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.cef.analysis_portfolio")

POSITIONS_PATH = config.INTERIM_DIR / "cef_clo_positions.parquet"

OUT_YIELD = config.FINAL_DIR / "cef_weighted_effective_yield.parquet"
OUT_CONCENTRATION = config.FINAL_DIR / "cef_portfolio_concentration.parquet"
OUT_TOP_HOLDINGS = config.FINAL_DIR / "cef_top_clo_holdings.parquet"


def _load_clo_positions() -> pd.DataFrame:
    if not POSITIONS_PATH.exists():
        return pd.DataFrame()
    df = read_parquet(POSITIONS_PATH)
    return df[df["is_clo"]].dropna(subset=["valUSD"])


def weighted_effective_yield() -> pd.DataFrame:
    clo = _load_clo_positions()
    if clo.empty:
        logger.warning("no CLO-tagged positions cached; run scrape_filings.py first")
        return pd.DataFrame(columns=["fund", "period", "weighted_yield", "n_positions", "total_fair_value"])
    rows = []
    for (fund, period), grp in clo.groupby(["fund", "period"]):
        rated = grp.dropna(subset=["annualizedRt"])
        weighted_yield = ((rated["annualizedRt"] * rated["valUSD"]).sum() / rated["valUSD"].sum()
                            if rated["valUSD"].sum() else None)
        rows.append({
            "fund": fund, "period": period, "weighted_yield": weighted_yield,
            "n_positions": len(grp), "total_fair_value": grp["valUSD"].sum(),
        })
    return pd.DataFrame(rows).sort_values(["fund", "period"])


def portfolio_concentration() -> pd.DataFrame:
    """HHI of position-level fair value within each fund's CLO sleeve, per period."""
    clo = _load_clo_positions()
    if clo.empty:
        return pd.DataFrame(columns=["fund", "period", "hhi", "top10_share"])
    rows = []
    for (fund, period), grp in clo.groupby(["fund", "period"]):
        total = grp["valUSD"].sum()
        if not total:
            continue
        shares = grp["valUSD"] / total
        hhi = (shares ** 2).sum() * 10_000
        top10_share = shares.sort_values(ascending=False).head(10).sum()
        rows.append({"fund": fund, "period": period, "hhi": hhi, "top10_share": top10_share})
    return pd.DataFrame(rows).sort_values(["fund", "period"])


def top_clo_holdings(n: int = 15) -> pd.DataFrame:
    clo = _load_clo_positions()
    if clo.empty:
        return pd.DataFrame(columns=["fund", "period", "name", "title", "valUSD", "pctVal"])
    latest = clo.sort_values("period").groupby("fund").apply(
        lambda g: g[g["period"] == g["period"].max()], include_groups=False
    ).reset_index(level=0)
    return (latest.sort_values(["fund", "valUSD"], ascending=[True, False])
            .groupby("fund").head(n)[["fund", "period", "name", "title", "valUSD", "pctVal"]])


def run() -> dict[str, pd.DataFrame]:
    yield_df = weighted_effective_yield()
    write_parquet(yield_df, OUT_YIELD, Provenance(parser="src.cef.analysis_portfolio.weighted_effective_yield", source_urls=[]))

    conc = portfolio_concentration()
    write_parquet(conc, OUT_CONCENTRATION, Provenance(parser="src.cef.analysis_portfolio.portfolio_concentration", source_urls=[]))

    top = top_clo_holdings()
    write_parquet(top, OUT_TOP_HOLDINGS, Provenance(parser="src.cef.analysis_portfolio.top_clo_holdings", source_urls=[]))

    logger.info("weighted_yield=%d rows, concentration=%d rows, top_holdings=%d rows",
                len(yield_df), len(conc), len(top))
    return {"yield": yield_df, "concentration": conc, "top_holdings": top}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
