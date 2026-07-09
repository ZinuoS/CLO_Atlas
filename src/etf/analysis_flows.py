"""AUM growth, flows, and market-share evolution for CLO ETFs (Section 1).

Honesty note on data limitations (see scrape_nav_flows.py docstring): no free
source publishes historical daily shares-outstanding for these ETFs, so a
true daily flow series (delta shares x NAV) can only accrete from the date
this project starts running scrape_nav_flows.py regularly — it is not back-
fillable. This module computes what the cached data actually supports:

  - `launch_timeline`: each fund's real first trading day, from full price
    history (solid, back-filled, VERIFIED).
  - `aum_by_scrape_date`: total market value per fund on each date we have
    holdings data for (sum of position market values) — a real AUM read for
    whichever funds/dates scrape_holdings.py has covered.
  - `flows_monthly`: Δ(shares_outstanding x nav) between consecutive NAV
    snapshots, in USD. Empty (by construction, not fabrication) until
    scrape_nav_flows.py has run on at least two distinct dates.
  - `market_share_evolution`: fund AUM as a share of total tracked CLO-ETF
    AUM, computed from whatever `aum_by_scrape_date` coverage exists.
  - `flow_event_study`: descriptive flow behavior in the window around each
    config.EVENTS entry. Requires overlapping flow history; returns an empty,
    clearly-labeled frame otherwise rather than interpolating one.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.etf.analysis_flows")

PRICES_PATH = config.INTERIM_DIR / "etf_prices.parquet"
HOLDINGS_PATH = config.INTERIM_DIR / "etf_holdings.parquet"
SNAPSHOTS_PATH = config.INTERIM_DIR / "etf_nav_snapshots.parquet"

OUT_LAUNCH = config.FINAL_DIR / "etf_launch_timeline.parquet"
OUT_AUM = config.FINAL_DIR / "etf_aum_by_scrape_date.parquet"
OUT_FLOWS = config.FINAL_DIR / "etf_flows_monthly.parquet"
OUT_SHARE = config.FINAL_DIR / "etf_market_share_evolution.parquet"
OUT_EVENT = config.FINAL_DIR / "etf_flow_event_study.parquet"


def launch_timeline() -> pd.DataFrame:
    prices = read_parquet(PRICES_PATH)
    clo_tickers = set(config.CLO_ETF_TICKERS)
    clo_prices = prices[prices["ticker"].isin(clo_tickers)]
    launch = clo_prices.groupby("ticker")["date"].min().reset_index().rename(columns={"date": "launch_date"})
    launch["issuer"] = launch["ticker"].map(lambda t: config.CLO_ETF_TICKERS[t]["issuer"])
    launch["tranche_focus"] = launch["ticker"].map(lambda t: config.CLO_ETF_TICKERS[t]["tranche_focus"])
    return launch.sort_values("launch_date").reset_index(drop=True)


def aum_from_holdings() -> pd.DataFrame:
    """Sum of position market values per fund per date — only covers funds/dates
    scrape_holdings.py has reached (currently JAAA/JBBB), but is a direct
    bottom-up read, useful as a cross-check against the snapshot-reported AUM.
    """
    if not HOLDINGS_PATH.exists():
        return pd.DataFrame(columns=["date", "fund", "aum_from_holdings"])
    holdings = read_parquet(HOLDINGS_PATH)
    aum = holdings.groupby(["date", "fund"])["market_value"].sum().reset_index()
    return aum.rename(columns={"market_value": "aum_from_holdings"})


def aum_by_scrape_date() -> pd.DataFrame:
    """Total net assets per fund per date. Primary source is the NAV-snapshot
    table's issuer-reported `total_assets` (covers all tracked funds); where a
    holdings-based sum also exists for the same fund/date it's attached as a
    cross-check column rather than overwriting the primary read.
    """
    if not SNAPSHOTS_PATH.exists():
        logger.warning("no NAV snapshot history cached yet; aum_by_scrape_date will be empty")
        return pd.DataFrame(columns=["date", "fund", "aum"])
    snaps = read_parquet(SNAPSHOTS_PATH).dropna(subset=["total_assets"])
    aum = snaps[["date", "ticker", "total_assets"]].rename(columns={"ticker": "fund", "total_assets": "aum"})
    holdings_aum = aum_from_holdings()
    if len(holdings_aum):
        aum = aum.merge(holdings_aum, on=["date", "fund"], how="left")
        both = aum.dropna(subset=["aum_from_holdings"])
        if len(both):
            gap = (both["aum"] - both["aum_from_holdings"]).abs() / both["aum"]
            logger.info("AUM cross-check (snapshot vs. sum-of-holdings) median relative gap: %.2f%%",
                        gap.median() * 100)
    return aum.sort_values(["date", "fund"]).reset_index(drop=True)


def flows_monthly() -> pd.DataFrame:
    """Flow = change in total net assets minus the return attributable to price
    movement over the same window (i.e. NAV-driven change is not a flow). We
    approximate this the standard way: flow_usd ~= delta(total_assets) -
    total_assets_prev * (nav_change_pct), which isolates the creation/
    redemption-driven component from the market-move component.
    """
    if not SNAPSHOTS_PATH.exists():
        logger.warning("no NAV snapshot history cached yet; flows_monthly will be empty")
        return pd.DataFrame(columns=["ticker", "month", "estimated_flow_usd"])
    snaps = read_parquet(SNAPSHOTS_PATH).dropna(subset=["total_assets", "nav"])
    if snaps["date"].nunique() < 2:
        logger.warning("NAV snapshot history has only %d distinct date(s); need >=2 to compute flows. "
                        "Run scrape_nav_flows.py again on a later day.", snaps["date"].nunique())
        return pd.DataFrame(columns=["ticker", "month", "estimated_flow_usd"])

    snaps = snaps.sort_values(["ticker", "date"]).copy()
    snaps["month"] = pd.to_datetime(snaps["date"]).dt.to_period("M")
    g = snaps.groupby("ticker")
    snaps["assets_prev"] = g["total_assets"].shift()
    snaps["nav_prev"] = g["nav"].shift()
    nav_return = (snaps["nav"] - snaps["nav_prev"]) / snaps["nav_prev"]
    snaps["estimated_flow_usd"] = (snaps["total_assets"] - snaps["assets_prev"]) - snaps["assets_prev"] * nav_return
    monthly = (snaps.dropna(subset=["estimated_flow_usd"])
               .groupby(["ticker", "month"])["estimated_flow_usd"].sum().reset_index())
    monthly["month"] = monthly["month"].astype(str)
    return monthly


def market_share_evolution(aum_df: pd.DataFrame) -> pd.DataFrame:
    if aum_df.empty:
        return pd.DataFrame(columns=["date", "fund", "aum", "market_share"])
    totals = aum_df.groupby("date")["aum"].transform("sum")
    out = aum_df.copy()
    out["market_share"] = out["aum"] / totals
    return out


def flow_event_study(flows_df: pd.DataFrame) -> pd.DataFrame:
    if flows_df.empty:
        logger.warning("flows_monthly is empty; flow_event_study returns an empty frame rather than interpolating")
        return pd.DataFrame(columns=["ticker", "event", "event_date", "flow_pre", "flow_post"])
    rows = []
    flows_df = flows_df.copy()
    flows_df["month_ts"] = pd.PeriodIndex(flows_df["month"], freq="M").to_timestamp()
    for ev in config.EVENTS:
        ev_date = pd.Timestamp(ev["date"])
        for ticker, grp in flows_df.groupby("ticker"):
            pre = grp[(grp["month_ts"] >= ev_date - pd.DateOffset(months=1)) & (grp["month_ts"] < ev_date)]
            post = grp[(grp["month_ts"] >= ev_date) & (grp["month_ts"] < ev_date + pd.DateOffset(months=1))]
            if pre.empty and post.empty:
                continue
            rows.append({
                "ticker": ticker, "event": ev["label"], "event_date": ev["date"],
                "flow_pre": pre["estimated_flow_usd"].sum() if len(pre) else None,
                "flow_post": post["estimated_flow_usd"].sum() if len(post) else None,
            })
    return pd.DataFrame(rows)


def run() -> dict[str, pd.DataFrame]:
    launch = launch_timeline()
    write_parquet(launch, OUT_LAUNCH, Provenance(parser="src.etf.analysis_flows.launch_timeline",
                                                    source_urls=[], notes="Derived from cached price history inception dates."))

    aum = aum_by_scrape_date()
    write_parquet(aum, OUT_AUM, Provenance(parser="src.etf.analysis_flows.aum_by_scrape_date", source_urls=[]))

    flows = flows_monthly()
    write_parquet(flows, OUT_FLOWS, Provenance(parser="src.etf.analysis_flows.flows_monthly", source_urls=[],
                                                  notes="Empty until >=2 NAV snapshot dates exist; not back-fillable from free data."))

    share = market_share_evolution(aum)
    write_parquet(share, OUT_SHARE, Provenance(parser="src.etf.analysis_flows.market_share_evolution", source_urls=[]))

    events = flow_event_study(flows)
    write_parquet(events, OUT_EVENT, Provenance(parser="src.etf.analysis_flows.flow_event_study", source_urls=[]))

    logger.info("launch_timeline=%d rows, aum_by_scrape_date=%d rows, flows_monthly=%d rows, "
                "market_share_evolution=%d rows, flow_event_study=%d rows",
                len(launch), len(aum), len(flows), len(share), len(events))
    return {"launch_timeline": launch, "aum_by_scrape_date": aum, "flows_monthly": flows,
            "market_share_evolution": share, "flow_event_study": events}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
