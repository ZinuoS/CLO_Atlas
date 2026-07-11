"""Market-maturation scorecard (Part C, closing slide) — every measurable
dimension of market maturity, one row per metric.

Built as a CURRENT-STATE snapshot table, not a multi-year indexed line
chart: most inputs (ETF AUM, TRACE volume, EFA holder composition) are
themselves single-date snapshots in this project (see each section's own
documented accretion limitation — repeated runs over time are what would
eventually make an indexed trend possible, not a one-time backfill). Only
Google Trends retail attention has genuine multi-year history among these
inputs; that is shown as its own trend, the rest as latest-value rows.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.future.analysis_maturation_scorecard")

ETF_AUM_PATH = config.FINAL_DIR / "etf_aum_by_scrape_date.parquet"
TRACE_VOLUME_PATH = config.FINAL_DIR / "trace_volume_by_band.parquet"
OPTIONS_PATH = config.INTERIM_DIR / "future_etf_options.parquet"
TRENDS_PATH = config.INTERIM_DIR / "future_google_trends.parquet"
HOLDER_PATH = config.FINAL_DIR / "clo_holder_composition.parquet"

OUT_SNAPSHOT = config.FINAL_DIR / "maturation_scorecard_snapshot.parquet"
OUT_TRENDS_INDEXED = config.FINAL_DIR / "maturation_scorecard_trends_indexed.parquet"


def snapshot_table() -> pd.DataFrame:
    rows = []
    if ETF_AUM_PATH.exists():
        etf = read_parquet(ETF_AUM_PATH)
        if len(etf):
            rows.append({"metric": "Total tracked CLO ETF AUM", "value": etf["aum"].sum(),
                         "unit": "USD", "as_of": str(etf["date"].max())})
    if TRACE_VOLUME_PATH.exists():
        trace = read_parquet(TRACE_VOLUME_PATH)
        if len(trace):
            rows.append({"metric": "TRACE-reported CLO trading volume", "value": trace["volume_usd_000s"].sum() * 1000,
                         "unit": "USD", "as_of": str(trace["date"].max())})
    if OPTIONS_PATH.exists():
        options = read_parquet(OPTIONS_PATH)
        if len(options):
            n_with_options = options["has_listed_options"].sum()
            rows.append({"metric": "CLO ETFs with listed options", "value": int(n_with_options),
                         "unit": f"of {len(options)} checked", "as_of": pd.Timestamp.today().date().isoformat()})
            rows.append({"metric": "Total options open interest (checked tickers)", "value": int(options["total_open_interest"].sum()),
                         "unit": "contracts", "as_of": pd.Timestamp.today().date().isoformat()})
    if HOLDER_PATH.exists():
        holders = read_parquet(HOLDER_PATH)
        if len(holders):
            n_types = holders["investor_type"].nunique()
            rows.append({"metric": "Distinct CLO investor types disclosed (Fed FEDS note)", "value": n_types,
                         "unit": "types", "as_of": "2018-12-31 (TO-VERIFY, dated)"})
    return pd.DataFrame(rows)


def trends_indexed() -> pd.DataFrame:
    """Google Trends series, each indexed to 100 at its own first available
    week — the one genuinely multi-year input in this scorecard."""
    if not TRENDS_PATH.exists():
        return pd.DataFrame(columns=["date", "query", "index_100"])
    df = read_parquet(TRENDS_PATH)
    if df.empty:
        return pd.DataFrame(columns=["date", "query", "index_100"])
    df = df.sort_values("date")
    out = []
    for query, grp in df.groupby("query"):
        grp = grp.sort_values("date")
        base = grp["interest"].iloc[0] or 1
        grp = grp.assign(index_100=grp["interest"] / base * 100)
        out.append(grp[["date", "query", "index_100"]])
    return pd.concat(out, ignore_index=True)


def run() -> dict[str, pd.DataFrame]:
    snapshot = snapshot_table()
    write_parquet(snapshot, OUT_SNAPSHOT, Provenance(
        parser="src.future.analysis_maturation_scorecard.snapshot_table", source_urls=[],
        notes="Current-state snapshot, not an indexed trend — most inputs are single-date snapshots in this project.",
    ))

    trends = trends_indexed()
    write_parquet(trends, OUT_TRENDS_INDEXED, Provenance(parser="src.future.analysis_maturation_scorecard.trends_indexed", source_urls=[]))

    logger.info("snapshot=%d metrics, trends_indexed=%d rows", len(snapshot), len(trends))
    return {"snapshot": snapshot, "trends_indexed": trends}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
