"""CLO trading liquidity from TRACE-sourced pricing tables (Section 4).

Real data from scrape_trace.py: trade counts, volume, and customer/dealer
split by rating band and vintage. Turnover (volume / amount outstanding)
isn't computable — SIFMA's outstanding-balance series is gated (see
scrape_sifma.py) — so this reports level/composition, not a turnover ratio,
and says so rather than guessing an outstanding figure. The volume-vs-ETF-
discount cross-section (Section 1 x Section 4) needs history on both sides
and degrades gracefully until enough daily runs accumulate.
"""
from __future__ import annotations

import logging

import pandas as pd

import config
from src.common.cache import Provenance, read_parquet, write_parquet

logger = logging.getLogger("clo_atlas.official.analysis_liquidity")

TRACE_PATH = config.INTERIM_DIR / "trace_clo_pricing.parquet"
ETF_DISLOCATION_PATH = config.FINAL_DIR / "etf_premium_discount_daily.parquet"

OUT_VOLUME = config.FINAL_DIR / "trace_volume_by_band.parquet"
OUT_SPLIT = config.FINAL_DIR / "trace_dealer_customer_split.parquet"
OUT_CROSS = config.FINAL_DIR / "trace_volume_vs_etf_discount.parquet"


def volume_by_band() -> pd.DataFrame:
    if not TRACE_PATH.exists():
        logger.warning("no TRACE data cached; run scrape_trace.py first")
        return pd.DataFrame(columns=["date", "rating_band", "vintage", "volume_usd_000s", "n_trades"])
    trace = read_parquet(TRACE_PATH)
    vol = trace[trace["metric"] == "VOLUME OF TRADES (000'S)"].rename(columns={"value": "volume_usd_000s"})
    n_trades = trace[trace["metric"] == "NUMBER OF TRADES"].rename(columns={"value": "n_trades"})
    merged = vol.merge(n_trades[["date", "rating_band", "vintage", "n_trades"]],
                        on=["date", "rating_band", "vintage"], how="left")
    return merged[["date", "rating_band", "vintage", "volume_usd_000s", "n_trades"]]


def dealer_customer_split() -> pd.DataFrame:
    if not TRACE_PATH.exists():
        return pd.DataFrame(columns=["date", "rating_band", "vintage", "side", "volume_usd_000s"])
    trace = read_parquet(TRACE_PATH)
    # block="volume_usd_000s" excludes the identically-labeled rows in the
    # "NUMBER OF TRADES" block (same CUSTOMER BUY/SELL/DEALER TO DEALER
    # labels, but counts, not dollars) — see scrape_trace.py's parser docstring.
    split = trace[(trace["block"] == "volume_usd_000s") &
                  trace["metric"].isin(["CUSTOMER BUY", "CUSTOMER SELL", "DEALER TO DEALER"])].copy()
    split = split.rename(columns={"metric": "side", "value": "volume_usd_000s"})
    return split[["date", "rating_band", "vintage", "side", "volume_usd_000s"]]


def volume_vs_etf_discount() -> pd.DataFrame:
    if not TRACE_PATH.exists() or not ETF_DISLOCATION_PATH.exists():
        logger.warning("need both TRACE and ETF premium/discount history for the cross-section; "
                        "returns empty until both have accreted multiple dates")
        return pd.DataFrame(columns=["date", "total_volume_usd_000s", "mean_abs_premium_discount"])
    trace = read_parquet(TRACE_PATH)
    etf = read_parquet(ETF_DISLOCATION_PATH)
    vol_by_date = trace[trace["metric"] == "VOLUME OF TRADES (000'S)"].groupby("date")["value"].sum()
    disc_by_date = etf.groupby("date")["premium_discount"].apply(lambda s: s.abs().mean())
    merged = pd.DataFrame({"total_volume_usd_000s": vol_by_date, "mean_abs_premium_discount": disc_by_date}).dropna()
    if len(merged) < 2:
        logger.info("cross-section has <2 overlapping dates so far; the volume-vs-discount episode read "
                     "accretes as both scrapers run on more days")
    return merged.reset_index()


def run() -> dict[str, pd.DataFrame]:
    vol = volume_by_band()
    write_parquet(vol, OUT_VOLUME, Provenance(parser="src.official.analysis_liquidity.volume_by_band", source_urls=[]))

    split = dealer_customer_split()
    write_parquet(split, OUT_SPLIT, Provenance(parser="src.official.analysis_liquidity.dealer_customer_split", source_urls=[]))

    cross = volume_vs_etf_discount()
    write_parquet(cross, OUT_CROSS, Provenance(parser="src.official.analysis_liquidity.volume_vs_etf_discount", source_urls=[]))

    logger.info("volume_by_band=%d rows, dealer_customer_split=%d rows, volume_vs_etf_discount=%d rows",
                len(vol), len(split), len(cross))
    return {"volume": vol, "split": split, "cross": cross}


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
